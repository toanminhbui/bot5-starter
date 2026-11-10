#!/usr/bin/env python3
"""Learn PD gains through reward-based parameter search in real Wasm bouts."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import secrets
import subprocess


ROOT = Path(__file__).resolve().parent
MAX_SEED = 2**64 - 1 - 100_001


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def rollout(root, package, seconds, seed):
    """Measure one exact package; rejected physics never supplies a reward."""
    command = ['sh', str(root / 'bot5'), 'test', str(package), '--seconds',
               str(seconds), '--seed', str(seed), '--json']
    record = {'seed': seed, 'valid': False, 'reward': None}
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=660)
    except subprocess.TimeoutExpired:
        return {**record, 'error': 'The engine exceeded its time limit.'}
    try:
        values = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
        result = next(value for value in reversed(values) if value.get('type') == 'result')
        summary = result['summary']
        if process.returncode != 0 or result.get('physics_valid') is not True or summary.get('valid') is not True:
            return {**record, 'error': str(summary.get('invalid_detail') or summary.get('reason') or 'Rejected rollout.')[:1000]}
        elapsed = summary['time_s']
        upright = summary['fighters'][0]['strict_posture_seconds']
        if not finite_number(elapsed) or not finite_number(upright) or elapsed < 0 or upright < 0:
            raise ValueError('Nonfinite or negative reward measurements.')
        # The physics tick may slightly overshoot the requested duration.
        reward = min(upright, elapsed, seconds)
        return {**record, 'valid': True, 'reward': reward,
                'elapsed_seconds': elapsed, 'reason': str(summary.get('reason', ''))}
    except (ValueError, TypeError, KeyError, IndexError, StopIteration, AttributeError):
        detail = process.stderr.strip() or 'The engine returned no valid result.'
        return {**record, 'error': detail[:1000]}


def evaluate(root, package, seconds, seeds):
    episodes = [rollout(root, package, seconds, seed) for seed in seeds]
    valid = all(episode['valid'] for episode in episodes)
    return {'valid': valid, 'mean_reward': sum(item['reward'] for item in episodes) / len(episodes) if valid else None,
            'episodes': episodes}


def search(root, *, source, output, trials, seconds, seed):
    """Compile once, search on training seeds, then test untouched held-out seeds."""
    output.mkdir(parents=True, exist_ok=False)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    base_path = output / 'base.bot.json'
    process = subprocess.run(['sh', str(root / 'bot5'), 'build', str(source), '--name',
                              'learning_bot', '--configuration', '{"kp":40,"kd":8}',
                              '--output', str(base_path)], capture_output=True, text=True, timeout=660)
    if process.returncode:
        raise ValueError((process.stderr.strip() or process.stdout.strip() or 'C++ compilation failed.')[:2000])
    base = json.loads(base_path.read_text(encoding='utf-8'))
    if base.get('format') != 'kickbox_portable_bot_v1' or base['bundle'].get('controller') != 'custom_wasm_v1':
        raise ValueError('Build did not produce a portable WebAssembly package.')
    candidates = output / 'candidates'
    candidates.mkdir()
    rng = random.Random(seed)
    training_seeds = [seed, seed + 1]
    held_out_seeds = [seed + 100_000, seed + 100_001]
    best = None
    baseline_reward = None
    print('Reward-based parameter search: maximize measured upright seconds.', flush=True)
    print('This tunes PD gains; it does not train fighting skills.', flush=True)
    with (output / 'trials.jsonl').open('x', encoding='utf-8') as stream:
        for trial in range(trials):
            if trial == 0:
                gains = {'kp': 40., 'kd': 8.}
            else:
                center = best['configuration'] if best else {'kp': 40., 'kd': 8.}
                gains = {key: min(high, max(low, center[key] * math.exp(rng.gauss(0., .55))))
                         for key, low, high in [('kp', 1., 300.), ('kd', .1, 60.)]}
            candidate = copy.deepcopy(base)
            candidate['bundle']['configuration'] = gains
            candidate['manifest']['version'] = str(trial + 1)
            path = candidates / ('trial-' + str(trial + 1).zfill(3) + '.bot.json')
            write_json(path, candidate)
            tested_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            measured = evaluate(root, path, seconds, training_seeds)
            if hashlib.sha256(path.read_bytes()).hexdigest() != tested_hash:
                raise ValueError('A tested package changed during evaluation.')
            record = {'trial': trial + 1, 'configuration': gains, 'package': str(path.relative_to(output)),
                      'package_sha256': tested_hash, **measured}
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            stream.flush()
            if trial == 0:
                baseline_reward = record['mean_reward']
            if record['valid'] and (best is None or record['mean_reward'] > best['mean_reward']):
                best = record
            score = format(record['mean_reward'], '.4f') + ' upright seconds' if record['valid'] else 'rejected; no reward'
            print('Trial ' + str(trial + 1) + '/' + str(trials) + ': ' + score, flush=True)
    if best is None:
        raise ValueError('Every candidate was rejected. See trials.jsonl for the engine errors.')
    selected = output / best['package']
    held_out = evaluate(root, selected, seconds, held_out_seeds)
    if hashlib.sha256(selected.read_bytes()).hexdigest() != best['package_sha256']:
        raise ValueError('The selected package changed during held-out evaluation.')
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError('The C++ source changed during this run; start a new run.')
    report = {'format': 'bot5_parameter_search_v1', 'algorithm': 'reward_based_parameter_search',
              'reward': 'Own strict-posture seconds, clipped to elapsed time and the episode budget; invalid episodes excluded.',
              'source_sha256': source_hash, 'seconds': seconds, 'sampling_seed': seed,
              'training_seeds': training_seeds, 'held_out_seeds': held_out_seeds,
              'trials': trials, 'baseline_mean_reward': baseline_reward, 'selected': best,
              'held_out': held_out, 'trained_fighting_policy': False}
    write_json(output / 'results.json', report)
    if not held_out['valid']:
        raise ValueError('The selected controller failed held-out physics checks. See results.json; no best.bot.json was created.')
    destination = output / 'best.bot.json'
    with destination.open('xb') as stream:
        stream.write(selected.read_bytes())
    print('Held-out mean: ' + format(held_out['mean_reward'], '.4f') + ' upright seconds.', flush=True)
    print('Saved tested package: ' + str(destination), flush=True)
    print('Inspect results.json before drawing conclusions from a short search.', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description='Tune the example C++ controller using real WebAssembly bouts. No ML dependencies needed.')
    parser.add_argument('--trials', type=int, default=6, help='Candidate configurations, including the baseline (default: 6).')
    parser.add_argument('--seconds', type=float, default=2., help='Maximum simulated seconds per bout (default: 2).')
    parser.add_argument('--seed', type=int, default=42, help='Reproducible sampling and training seed (default: 42).')
    parser.add_argument('--source', type=Path, default=ROOT / 'my_bot.cpp', help='A C++ controller accepting kp/kd configuration.')
    parser.add_argument('--output', type=Path, help='A new run directory; existing directories are never overwritten.')
    args = parser.parse_args()
    if not 1 <= args.trials <= 1000 or not math.isfinite(args.seconds) or not 0 < args.seconds <= 30 or not 0 <= args.seed <= MAX_SEED:
        parser.error('Use 1–1000 trials, seconds in (0,30], and a seed from 0 through ' + str(MAX_SEED) + '.')
    output = args.output or ROOT / 'runs' / ('search-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3))
    try:
        search(ROOT, source=args.source.expanduser().absolute(), output=output.expanduser().absolute(),
               trials=args.trials, seconds=args.seconds, seed=args.seed)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        parser.exit(2, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
