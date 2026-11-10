# Training guide

This guide walks through the learning example included in this repository:
run a small search, inspect its results, change what it learns, and upload the
selected controller.

The current learner searches controller parameters using rewards from real
WebAssembly simulations. It is not a neural-network RL trainer. No GPU or
additional Python packages are needed.

## 1. Set up and check your controller

Follow the [README setup instructions](README.md), then run these commands from
the starter repository:

```sh
./bot5 setup
./bot5 build my_bot.cpp
./bot5 test my_bot.bot.json --seconds 2
```

The example controller holds the joint angles measured at reset. It returns:

```text
torque = kp × (target angle − current angle) − kd × joint velocity
```

The requested torque is clamped to each joint's cap. `kp` controls correction
strength; `kd` controls damping. Increasing either value is not automatically
better.

The local opponent is a scripted guard. There is currently no opponent-selection
flag in this learner or the local test command.

## 2. Run a small search first

```sh
./bot5 python learn.py --trials 2 --seconds 0.5 --seed 42 \
  --output runs/first-search
```

This is a workflow check, not a meaningful fighting benchmark. Once it works,
start a longer experiment in a **new** directory:

```sh
./bot5 python learn.py --trials 50 --seconds 10 --seed 42 \
  --output runs/balance-001
```

| Option | Default | What you can change |
| --- | --- | --- |
| `--trials` | `6` | Number of candidate configurations, including the baseline; 1–1000. |
| `--seconds` | `2` | Maximum simulated seconds per bout; greater than 0 and at most 30. |
| `--seed` | `42` | Nonnegative integer controlling parameter sampling and evaluation seeds. The command validates its upper bound. |
| `--source` | Repository's `my_bot.cpp` | Another C++ controller accepting `kp` and `kd` configuration. |
| `--output` | Unique directory under `runs/` | A directory that does not already exist. |

Run `./bot5 python learn.py --help` for the available options.
Each invocation starts a fresh search. Edit the controller and learning script
in the starter repository, rather than the cached tools under `.bot5/`.

## 3. Understand what happens in a run

1. The script compiles the chosen C++ controller into WASM once. The initial
   configuration is `{"kp":40,"kd":8}`; the build uses the default lean body.
2. Trial 1 evaluates that baseline. Later trials randomly perturb the current
   best valid configuration, with `kp` bounded to 1–300 and `kd` to 0.1–60.
3. Each candidate is packaged with its own configuration and evaluated on two
   training seeds: `seed` and `seed + 1`.
4. The reward is own upright time:
   `min(strict_posture_seconds, elapsed_seconds, requested_seconds)`.
   Candidate quality is the mean reward across the training bouts.
5. The highest-scoring valid candidate is checked on two held-out seeds:
   `seed + 100000` and `seed + 100001`. These do not select the winner.
6. If the held-out simulations are valid, the script copies the exact selected
   package to `best.bot.json`.

An invalid episode has no reward; it is not treated as an ordinary loss with
zero reward. All episodes must be valid for a candidate's mean to be accepted.

With the default seed lists, `N` trials require `2 × N + 2` bouts. For 50
trials at 10 seconds, that is up to 1,020 simulated seconds, plus compilation
and process startup. Wall-clock time depends on your computer and controller.

The first trial wins ties, so a short task on which every candidate stays
upright may keep the baseline. Held-out validity does not require an improved
reward.

## 4. Read the results before uploading

A successful run produces:

```text
runs/balance-001/
  base.bot.json
  base.bot.wasm
  candidates/
    trial-001.bot.json
    ...
  trials.jsonl
  results.json
  best.bot.json
```

- `trials.jsonl` records each candidate's configuration, package hash, per-seed
  outcomes, validity, and mean reward.
- `results.json` records the baseline training reward, selected candidate,
  held-out results, source hash, seeds, and episode duration.
- `best.bot.json` contains the compiled controller and winning configuration.
  Each run assigns fresh upload versions.

Print the main measurements with the included Python:

```sh
./bot5 python -c 'import json; from pathlib import Path; r=json.loads(Path("runs/balance-001/results.json").read_text()); print("Baseline training:", r["baseline_mean_reward"]); print("Selected training:", r["selected"]["mean_reward"]); print("Selected configuration:", r["selected"]["configuration"]); print("Held-out:", r["held_out"])'
```

Compare the baseline and selected training scores under the same conditions.
The script does not evaluate the baseline on the held-out seeds, so that
comparison is not present in `results.json`. A different seed is only useful
if it changes relevant conditions; this example's reset method ignores its seed,
and distinct seeds alone do not prove diverse behavior.

Repeat with a different sampling seed and a fresh output directory to check
whether the search result is stable. Do not repeatedly tune against the same
held-out seeds and continue treating them as unseen evaluation data.

## 5. Change the experiment

### Train a custom controller

Follow the README's [custom controller instructions](README.md#write-a-custom-controller)
for the interface and [build options](README.md#build-and-configure) for
configuration and packaging. The learner accepts another source through
`--source`.

Copy the example so you can compare it with your changes:

```sh
cp my_bot.cpp balance_bot.cpp
./bot5 python learn.py --source balance_bot.cpp --trials 10 --seconds 2 \
  --seed 43 --output runs/custom-balance-001
```

Initially this runs the same controller. Change target poses, joint-specific
control, or movement logic in `balance_bot.cpp`, keeping the factory functions,
finite torque output, joint ordering, and torque caps intact. Keep accepting
`kp` and `kd` until you also update the search script.

The next run recompiles the source. Do not edit that source while a run is
active: the script checks its hash and rejects a changed source at the end.

### Parameter ranges and exploration: edit search()

In `learn.py`, locate the candidate-generation code in `search()`:

```python
gains = {key: min(high, max(low, center[key] * math.exp(rng.gauss(0., .55))))
         for key, low, high in [('kp', 1., 300.), ('kd', .1, 60.)]}
```

For a narrower search, for example, replace it with:

```python
gains = {key: min(high, max(low, center[key] * math.exp(rng.gauss(0., .20))))
         for key, low, high in [('kp', 10., 100.), ('kd', 1., 20.)]}
```

The Gaussian standard deviation controls multiplicative perturbations: smaller
values explore closer to the best configuration. Keep the baseline and fallback
center within your chosen ranges. This sampler needs positive values; parameters
that can be zero or negative need a different sampling rule.

To add a new parameter, update all of these together:

1. C++ configuration validation, storage, and the behavior using the parameter.
   The example rejects unknown configuration fields.
2. The initial build's `--configuration`, trial-1 configuration, and fallback
   center inside `search()`.
3. The candidate sampler and bounds.

A parameter must change controller behavior to be learnable. Start with one
additional parameter and check it manually at two values before searching.

### Reward: edit rollout()

`rollout()` reads the engine's final summary. To inspect the actual fields:

```sh
./bot5 test my_bot.bot.json --seconds 2 --seed 42 --json
```

This prints JSON lines: a contract and a result. The result contains `summary`;
the learner uses fighter index `0` for your bot. Use recorded fields rather than
inventing metric names.

A small first exercise is normalizing upright reward to the requested duration.
Replace:

```python
reward = min(upright, elapsed, seconds)
```

with:

```python
reward = min(upright, elapsed, seconds) / seconds
```

For valid measurements this gives a reward from 0 to 1. At a fixed bout duration
it preserves candidate ordering; it changes units, not the learned behavior.

For movement or fighting rewards, first implement a controller capable of those
behaviors, then select available measurements that reflect the goal. Keep
invalid-physics checks and finite-number validation. Reward only measured legal
outcomes; giving reward for attempted attacks can favor motion without contact.

Whenever you change the reward, also update the report's `reward` description
and the console strings containing "upright seconds". Use a new output directory
and compare only runs with matching reward definitions and durations.

### Seeds and body

To increase evaluation coverage, edit `training_seeds` and `held_out_seeds` in
`search()`. Keep both lists nonempty and disjoint, stay within unsigned 64-bit
seed limits, and include the resulting extra simulations in your runtime budget.

To change body profile, add `'--profile', 'balanced'` (or `'power'`) to the
initial build command in `search()`. Every candidate inherits that package's
profile. Train and evaluate the chosen body instead of relabeling a finished
package.

## 6. Test and upload the selected package

```sh
./bot5 test runs/balance-001/best.bot.json --seconds 30 --seed 2026 \
  --frames runs/balance-001/replay.jsonl
```

This tests longer on a seed outside the example search and saves replay frames.
`--frames` writes JSON lines; it does not open a visual viewer.

Sign in at [bot5.tbui.dev](https://bot5.tbui.dev), verify your email, and upload
the same tested `runs/balance-001/best.bot.json`. Do not rebuild the original
source with default settings to submit the winner: that would discard its
selected configuration. Use the arena's fight creation flow to evaluate
against available arena bots.

## 7. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Output directory already exists | Pick a new directory; the learner has no resume mode and never overwrites a run. |
| C++ compilation fails | Run `./bot5 build your_bot.cpp` separately and inspect the compiler error. |
| Every candidate is rejected | Inspect per-episode errors in `trials.jsonl`; verify the controller's configuration fields, finite torques, and runtime budget. |
| No best.bot.json | The run may be interrupted, all candidates may be invalid, or held-out validity/source checks may have failed. Inspect logs and `results.json` if present. |
| All scores are equal | The task may saturate the reward, the horizon may be too short, or the parameters may not affect behavior. Check before increasing trial count. |
| Search takes too long | Reduce trials or duration for debugging. Bouts execute sequentially; there is no worker-count option. |
