# Make a Bot5 bot

Write C++, test its WebAssembly in the arena engine, and upload the same package.

```sh
git clone https://github.com/toanminhbui/bot5-starter.git
cd bot5-starter
./bot5 build my_bot.cpp
./bot5 test my_bot.bot.json
```

The first build downloads the compiler, engine, and Python automatically. Later
builds and tests work offline. No account, compiler installation, or Python setup
is needed. Git, curl, and tar must be available.

Use Ubuntu 24.04 or compatible Linux on x86-64, including Windows WSL2. On Windows, clone inside your WSL2 Linux home folder.

Use an Apple Silicon Mac with macOS 15 or newer.

## Change your bot

Edit `my_bot.cpp`, then repeat the build and test commands. The example holds its
starting pose; it is a starting point for learning.

`reset()` starts each fight. `joint_torques(input)` receives public match state
and your joint measurements 4,000 times per simulated second. Return one finite
torque per owned joint, in the supplied order and within its torque cap. Keep the
factory functions at the bottom of the file.

Controllers have no filesystem or network access. Include inference code and
learned weights in your C++.

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
guarantee a win. For manual C++ builds, use a new `--version` for each uploaded update.

Run `./bot5 --help` for commands and `./bot5 python learn.py --help` for search
options. `./bot5 setup` downloads the tools without building a bot.
