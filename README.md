# Make a Bot5 bot

Write a C++ controller, compile it into WebAssembly (WASM), test it in the arena
engine, and upload the generated package. This README covers the complete
build-to-fight workflow. The [training guide](TRAINING.md) explains learning
runs, rewards, and parameter tuning.

## Get the tools

With Git, curl, and tar available, run these commands.

```sh
git clone https://github.com/toanminhbui/bot5-starter.git
cd bot5-starter
./bot5 setup
./bot5 build my_bot.cpp
./bot5 test my_bot.bot.json
```

Use Ubuntu 24.04 or compatible Linux on x86-64, including Windows WSL2. On Windows, clone inside your WSL2 Linux home folder.

Use an Apple Silicon Mac with macOS 15 or newer.

Setup downloads the pinned creator kit into `.bot5/` and verifies its size
and SHA-256. The kit includes the WASI SDK 34.0 Clang C++ compiler, headers,
libraries, arena engine, WASM runtime, and Python. Build and test also prepare
the tools automatically when needed. After setup, builds and tests work offline.

To get a complete offline kit directly, download the
[Linux / WSL2 archive](https://github.com/toanminhbui/bot5-starter/releases/download/creator-2026-11-10/bot5-creator-linux-x86_64.tar.gz)
or [Apple Silicon Mac archive](https://github.com/toanminhbui/bot5-starter/releases/download/creator-2026-11-10/bot5-creator-macos-arm64.tar.gz).
Extract it and open a terminal in `bot5-creator-sdk` to use the build and test
commands below. Use this starter repository for the training workflow, which
also needs `learn.py` and `TRAINING.md`.

## Write a custom controller

Edit `my_bot.cpp`, or start another controller by copying the example.

```sh
cp my_bot.cpp my_controller.cpp
./bot5 build my_controller.cpp
./bot5 test my_controller.bot.json
```

The example holds its starting joint angles. Adapt its `JointController`
implementation to make your fighter move, defend, and strike.

- `reset()` initializes each fight. Keep controller state on its instance.
- `joint_torques(input)` receives public match state in `input.public_state`
  and your joint measurements in `input.owned_joints`, currently 4,000 times
  per simulated second.
- Return one finite torque in newton-metres per owned joint, in the supplied
  order and within that joint's torque cap.
- Retain the exported factory functions at the bottom of the example.

The engine applies physical torque, speed, power, fatigue, and damage limits.
The compiler targets WASM with C++20. Compile learned inference code and
weights/data into the controller, for example as constant arrays. The
controller operates with its embedded data and packaged configuration, with
zero host imports and no filesystem or network access.

## Build and configure

```sh
./bot5 build my_bot.cpp --name my_bot --profile lean --version 1 \
  --configuration '{"kp":40,"kd":8}'
```

Use `--configuration-file settings.json` for a configuration object stored in
a file. Configuration is limited to 16 KiB. The example accepts `kp` and `kd`.
Your own controller defines and validates its accepted settings.

Choose `lean` (default), `balanced`, or `power` for the body profile. Use
`--output path/to/my_bot.bot.json` to choose the package location.

Compilation produces a WASM module, which the builder then packages.

```text
C++ controller + embedded inference/weights
  → WASM compiler → my_bot.bot.wasm
  → package with configuration and body profile → my_bot.bot.json
```

The generated `.bot.json` contains the actual WASM bytes, encoded as base64,
their size and SHA-256, controller configuration, body profile, name, and version.
This makes the generated JSON a complete upload containing the custom controller.
The adjacent raw `.wasm` is available for local inspection. Module size is
limited to 8 MiB and the complete JSON upload to 16 MiB.

## Test locally

```sh
./bot5 test my_bot.bot.json --seconds 10 --seed 42
./bot5 test my_bot.bot.json --seconds 10 --seed 42 --frames replay.jsonl
```

The runner loads the WASM from your package and simulates it against a scripted
guard opponent in the bundled arena engine. It uses the package's configuration
and body profile and prints physics validity, simulated time, and the result.
The default duration is 3 simulated seconds, with a maximum of 30.

The guard tries to maintain its stance and guard under physics. Opponent
selection is currently available through the hosted arena's Create a fight
flow. Locally, `--frames` saves physics frames as JSON lines for inspection.
Visual fight playback is available on the website.

Use `--json` to print the engine contract and result as JSON lines.
The test leaves the package unchanged. Fix any reported controller or physics
error and rebuild before submitting.

## Train your controller

Start with a small learning experiment.

```sh
./bot5 python learn.py --trials 2 --seconds 0.5 --seed 42 \
  --output runs/first-search
```

The learner searches `kp` and `kd` to maximize measured upright time. It
compiles the controller once, evaluates configurations in WASM, and checks the
selected configuration on held-out seeds. Results, trial logs, and the selected
`best.bot.json` are written under the new output directory.

Follow the [training guide](TRAINING.md) for longer runs, custom controller
training with `--source`, editable parameter ranges and rewards, evaluation,
and troubleshooting. Start with the
[custom controller instructions above](#write-a-custom-controller) when adapting
your own C++.

## Upload and fight

1. Open [bot5.tbui.dev](https://bot5.tbui.dev), create an account or sign in,
   and verify your email.
2. Open Upload a bot, choose your tested `.bot.json`, and press Upload bot.
   For a learning run, select that run's `best.bot.json` to preserve its
   selected configuration.
3. Choose Create a fight, select your bot and an available arena opponent,
   then watch the bout or its replay.

The website validates and runs the WASM contained in the upload. Custom
controllers use the same package-based submission flow as the example.

Bouts last up to 30 simulated seconds. Physical contact earns fractional
contact points, and a fall or damage stoppage can end a bout earlier.
Use arena fights to evaluate your bot's behavior against other controllers.

For each manually built update, use a fresh version and repeat your chosen
profile and configuration options in the build command.

```sh
./bot5 build my_bot.cpp --name my_bot --profile lean --version 2 \
  --configuration '{"kp":40,"kd":8}'
./bot5 test my_bot.bot.json
```

Each learning run assigns fresh upload versions automatically. Upload the
selected package from that run.

For an existing supported policy export, download the website's
[policy exporter](https://bot5.tbui.dev/package_bot.py) and follow its `--help`
instructions to create a package compatible with that policy's controller.

## Troubleshooting

| Problem | Next step |
| --- | --- |
| Setup rejects the computer | Check the OS and architecture requirements above. Run Windows commands inside WSL2. |
| Download fails | Check your connection and rerun `./bot5 setup`. If you already have the pinned release archive, use `./bot5 setup --archive /path/to/archive.tar.gz`. |
| Build fails | Read the compiler error, check the controller interface and factory functions, and verify configuration fields. |
| Test reports an error | Inspect the result and `--json` output. Check finite torques, joint ordering, configuration, and controller runtime cost. |
| Upload fails | Select the generated `.bot.json`, verify your email, and check package size and version. |
| Learning run fails or scores stay flat | Follow the [training troubleshooting section](TRAINING.md#7-troubleshooting). |

Run `./bot5 --help`, `./bot5 build --help`, `./bot5 test --help`, or
`./bot5 python learn.py --help` for command options.
