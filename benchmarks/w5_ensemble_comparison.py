"""W5 independent synthetic benchmark comparing HM-P1e and opt-in ensemble.

Predict-before-update. Same Bernoulli outcomes and local SQLite durability.
No LLMs, external observations, paid resources or production workloads.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e, Observation, _probabilities
from openworld_superkernel.hyper_memory_ensemble import EnsembleHyperMemory
from openworld_superkernel.memory_contracts import MemoryEvent, Provenance

SCENARIOS = ('stable', 'abrupt', 'gradual', 'alternating', 'noise')
MODELS = ('static', 'fast', 'slow', 'gate', 'ensemble')


def oracle(agent: int, t: int, horizon: int, scenario: str) -> float:
    if scenario not in SCENARIOS:
        raise ValueError('unknown scenario')
    p = 0.8 if agent % 2 else 0.2
    if scenario == 'stable':
        return p
    if scenario == 'abrupt':
        return p if t < horizon // 2 else 1-p
    if scenario == 'gradual':
        return p + (1-2*p)*t/max(1,horizon-1)
    if scenario == 'alternating':
        return p if (t//max(1,horizon//4))%2==0 else 1-p
    return 0.5


def draw(agents: int, steps: int, seed: int, scenario: str):
    if agents<1 or steps<1 or scenario not in SCENARIOS:
        raise ValueError('invalid simulation input')
    rngs = [random.Random(seed + 100_003*a) for a in range(agents)]
    for t in range(steps):
        yield [(a, t, int(rngs[a].random() < oracle(a,t,steps,scenario)))
               for a in range(agents)]


def physical_bytes(path: Path) -> int:
    return sum(p.stat().st_size for ext in ('','-wal','-shm')
               if (p:=Path(str(path)+ext)).exists())


def p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return sorted(xs)[math.ceil(0.95*len(xs))-1]


def sample(agent: int, t: int, y: int) -> Observation:
    return Observation(event=MemoryEvent(
        event_id=f'agent-{agent}:t-{t}', owner_id='synthetic',
        event_type='telemetry', provenance=Provenance.SIMULATED,
        payload=b'', reconstructable=True),
        agent_id=f'agent-{agent}', sequence_number=t+1, outcome=y)


def evaluate(*, agents: int, days: int, seed: int, scenario: str) -> dict:
    with tempfile.TemporaryDirectory(prefix='openworld-w5-ensemble-') as directory:
        full_path = Path(directory)/'full.sqlite'
        gate_path = Path(directory)/'gate.sqlite'
        ensemble_path = Path(directory)/'ensemble.sqlite'
        full = sqlite3.connect(full_path, isolation_level=None)
        full.execute('PRAGMA journal_mode=WAL')
        full.execute('PRAGMA synchronous=FULL')
        full.execute('CREATE TABLE history(agent_id INTEGER, step INTEGER, outcome INTEGER, '
                     'PRIMARY KEY(agent_id,step)) WITHOUT ROWID')
        gate = HyperMemoryP1e(gate_path)
        ensemble = EnsembleHyperMemory(ensemble_path)
        predictions = {name:[] for name in MODELS}
        outcomes=[]
        modes={'static':0, 'fast':0, 'slow':0}
        durations={'full_history':[], 'gate':[], 'ensemble':[]}
        peaks={'full_history':0,'gate':0,'ensemble':0}
        start_cpu=time.process_time()
        try:
            for batch in draw(agents,days,seed,scenario):
                incoming=[]
                for agent,t,y in batch:
                    agent_id=f'agent-{agent}'
                    prev=gate.get_state(owner_id='synthetic', agent_id=agent_id,
                                        requester_owner_id='synthetic')
                    ps=_probabilities(prev)
                    g,selected=gate.predict(owner_id='synthetic',agent_id=agent_id,
                                            requester_owner_id='synthetic')
                    h,_=ensemble.predict(owner_id='synthetic',agent_id=agent_id,
                                         requester_owner_id='synthetic')
                    for name in ('static','fast','slow'):
                        predictions[name].append(ps[name])
                    predictions['gate'].append(g)
                    predictions['ensemble'].append(h)
                    modes[selected]+=1
                    outcomes.append(y)
                    incoming.append(sample(agent,t,y))

                before=time.perf_counter()
                full.execute('BEGIN IMMEDIATE')
                try:
                    full.executemany('INSERT INTO history VALUES(?,?,?)',
                                     [(a,t,y) for a,t,y in batch])
                    full.execute('COMMIT')
                except BaseException:
                    full.execute('ROLLBACK')
                    raise
                durations['full_history'].append(time.perf_counter()-before)

                before=time.perf_counter()
                n=gate.apply_batch(incoming,requester_owner_id='synthetic')
                durations['gate'].append(time.perf_counter()-before)
                if n != agents:
                    raise AssertionError('gate lost observations')
                before=time.perf_counter()
                n=ensemble.apply_batch(incoming,requester_owner_id='synthetic')
                durations['ensemble'].append(time.perf_counter()-before)
                if n != agents:
                    raise AssertionError('ensemble lost observations')
                for key,path in [('full_history',full_path),('gate',gate_path),('ensemble',ensemble_path)]:
                    peaks[key]=max(peaks[key],physical_bytes(path))
            online={k:physical_bytes(v) for k,v in
                    [('full_history',full_path),('gate',gate_path),('ensemble',ensemble_path)]}
            full.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            gate.checkpoint()
            ensemble.checkpoint()
            compact={k:physical_bytes(v) for k,v in
                     [('full_history',full_path),('gate',gate_path),('ensemble',ensemble_path)]}
            return {
                'scenario':scenario,'seed':seed,'agents':agents,'days':days,
                'updates':agents*days,
                'brier':{k:sum((p-y)**2 for p,y in zip(predictions[k],outcomes))/len(outcomes)
                         for k in MODELS},
                'gate_selections':modes,
                'storage_bytes':{'peak_online':peaks,'end_online':online,'after_checkpoint':compact},
                'write_seconds':{k:sum(v) for k,v in durations.items()},
                'p95_daily_write_ms':{k:1000*p95(v) for k,v in durations.items()},
                'combined_cpu_seconds':time.process_time()-start_cpu,
            }
        finally:
            full.close()
            gate.close()
            ensemble.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agents',type=int,default=30)
    parser.add_argument('--days',type=int,default=40)
    parser.add_argument('--seeds',type=int,default=5)
    parser.add_argument('--seed-start',type=int,default=3001)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.agents<1 or args.days<1 or args.seeds<1:
        parser.error('positive agents, days and seeds required')
    results=[evaluate(agents=args.agents,days=args.days,seed=args.seed_start+i,
                      scenario=scenario) for scenario in SCENARIOS
             for i in range(args.seeds)]
    report={
        'environment':{'python':sys.version.split()[0], 'sqlite':sqlite3.sqlite_version,
                       'platform':platform.platform(), 'pid_isolated':True},
        'spec':{'agents':args.agents,'days':args.days,'seeds':args.seeds,
                'seed_start':args.seed_start,'scenarios':SCENARIOS,
                'durability':'WAL+synchronous FULL, single local process'},
        'averages_by_scenario':{
            scenario:{model:statistics.mean(r['brier'][model] for r in results
                       if r['scenario']==scenario) for model in MODELS}
            for scenario in SCENARIOS},
        'results':results,
        'limitations':['Synthetic Bernoulli outcomes only',
                       'Full history preserves past events; compact predictors do not',
                       'Predictor training state scales with K; exact ledger may grow',
                       'SQLite WAL+SHM bytes are included, not filesystem/replica copies',
                       'CPU combined across systems; no per-model CPU attribution',
                       'No held-out seed is used to tune parameters in this script',
                       'No network, LLM, external source authentication or production claims']
    }
    serialized=json.dumps(report,indent=2)
    if args.out:
        args.out.write_text(serialized+'\n')
    print(json.dumps({'environment':report['environment'], 'spec':report['spec'],
                      'averages_by_scenario':report['averages_by_scenario']},indent=2))

if __name__=='__main__':
    main()
