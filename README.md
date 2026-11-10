# Make a Bot5 bot

Build your custom C++ controller into WebAssembly (WASM), test it in the arena
engine, then upload the generated package.

```text
my_bot.cpp + embedded weights/data
  → WASM compiler → my_bot.bot.wasm
  → package with configuration and body profile → my_bot.bot.json
  → local test → website upload
```

**A controller description or JSON pointing to local files is not enough.** The
generated `.bot.json` contains the compiled controller itself, encoded inside
the JSON. This is why the final upload needs only one file.

```sh
git clone https://github.com/toanminhbui/bot5-starter.git
cd bot5-starter
./bot5 setup
./bot5 build my_bot.cpp
./bot5 test my_bot.bot.json
```

Git, curl, and tar must be available. `./bot5 setup` downloads the pinned creator
kit, including the **WASI SDK 34.0 Clang C++ → WASM compiler**, C++ headers and
libraries, arena engine, local WASM runner, and Python. It checks the download's
size and SHA-256 before installing the kit under `.bot5/`.

You do not need to install a system C++ compiler, Emscripten, or Python. Build
and test also run setup automatically if needed. After setup, later builds and
tests work offline. An account is needed only when uploading to the website.

Use Ubuntu 24.04 or compatible Linux on x86-64, including Windows WSL2. On Windows, clone inside your WSL2 Linux home folder.

Use an Apple Silicon Mac with macOS 15 or newer.

## Change your bot

Edit `my_bot.cpp`, then repeat the build and test commands. The example holds its
starting pose; it is a starting point for learning.

`reset()` starts each fight. `joint_torques(input)` receives public match state
and your joint measurements 4,000 times per simulated second. Return one finite
torque per owned joint, in the supplied order and within its torque cap. Keep the
factory functions at the bottom of the file.

For an existing custom controller, adapt it to the `JointController` interface
shown in `my_bot.cpp` and retain the exported factory functions. The compiler
targets WASM with C++20; a native `.so`, `.dll`, or executable cannot be used
as the uploaded controller.

Controllers have no filesystem or network access. Compile inference code and
learned weights/data into your C++ module, for example as constant arrays.
Replace runtime model-file loading with embedded data. A checkpoint, Python
training script, or path to a weights file is not executable controller code.

Small settings can be packaged separately from the module's code:

```sh
./bot5 build my_bot.cpp --profile lean --version 1 \
  --configuration '{"kp":40,"kd":8}'
./bot5 test my_bot.bot.json
```

Use `--configuration-file settings.json` instead for a JSON configuration object
of at most 16 KiB. Body profiles are `lean` (default), `balanced`, and `power`.

## What the build produces

- `my_bot.bot.wasm`: your compiled controller, including any embedded inference
  code and weights. Keep this for local inspection.
- `my_bot.bot.json`: the upload package, containing those WASM bytes as base64,
  their byte count and SHA-256, controller configuration, body profile, name,
  and version. It does not reference the raw WASM file on your computer.

`./bot5 test my_bot.bot.json` runs the module **from the package** in WebAssembly
inside the bundled arena engine, using its configuration and body profile.
It leaves the package unchanged. Upload that same tested JSON.

The website validates and runs the packaged WASM; it does not compile your C++
or fetch model files from your computer. Custom WASM controllers do not require
the arena operator to register a native library first.

## Try learning

```sh
./bot5 python learn.py
```

This small reward-based search tunes the example's controller gains using time
spent upright. It compiles once, evaluates configurations in WebAssembly, and
checks the winner on separate seeds. Results and the tested `best.bot.json` go
in a new `runs/` folder. No additional packages or GPU are needed.
Upload `best.bot.json` directly to preserve the selected gains.
Each learning run uses a fresh upload version.

This is an introductory parameter search. It does not train a neural network or
produce a competitive fighter. Change the controller and reward as you learn.

## Upload

Sign in at [bot5.tbui.dev](https://bot5.tbui.dev), verify your email, and upload
the tested **`.bot.json`**. A valid local test checks execution; it does not
guarantee a win. Select the generated package, rather than a hand-written JSON,
source file, raw WASM module, or training checkpoint. The JSON upload limit is
16 MiB; the compiled module limit is 8 MiB.

For an update, rebuild with a new version and test again:

```sh
./bot5 build my_bot.cpp --version 2
./bot5 test my_bot.bot.json
```

Repeat any profile and configuration options used for your bot; a new build
uses defaults for options you omit. Upload the newly tested `my_bot.bot.json`.
Use a fresh version for each uploaded update.

Run `./bot5 --help` for commands and `./bot5 python learn.py --help` for search
options. `./bot5 setup` downloads the tools without building a bot.
