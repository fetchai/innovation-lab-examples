# Azle Hello World

- [Installation](#installation)
- [Deployment](#deployment)
- [Testing](#testing)

Azle helps you to build secure decentralized/replicated servers in TypeScript or JavaScript on [ICP](https://internetcomputer.org/). The current replication factor is [13-40 times](https://dashboard.internetcomputer.org/subnets).

## Experimental Mode

This example can only be run in Azle's experimental mode.

Azle runs in experimental mode through explicitly enabling a flag in `dfx.json` or certain CLI commands.

This mode is intended for developers who are willing to accept the risk of using an alpha or beta project. Its focus is on quickly enabling new features and functionality without requiring the time and other resources necessary to advance them to the stable mode. The Node.js standard libary, npm ecosystem, and HTTP server functionality are also major areas of focus.

> NOTE: Keep clearly in mind that the experimental mode fundamentally changes the Azle Wasm binary. It is not guaranteed to be secure or stable in API changes or runtime behavior. If you enable the experimental mode, even if you only use APIs from the stable mode, you are accepting a higher risk of bugs, errors, crashes, security exploits, breaking API changes, etc.

## Installation

> Windows is only supported through a Linux virtual environment of some kind, such as [WSL](https://learn.microsoft.com/en-us/windows/wsl/install)

You will need [Node.js](#nodejs) and [dfx](#dfx) to develop ICP applications with Azle:

### Node.js

It's recommended to use nvm to install the latest LTS version of Node.js:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
```

Restart your terminal and then run:

```bash
nvm install --lts
```

Check that the installation went smoothly by looking for clean output from the following command:

```bash
node --version
```

### dfx

Install the dfx command line tools for managing ICP applications:

```bash
DFX_VERSION=0.25.0 sh -ci "$(curl -fsSL https://internetcomputer.org/install.sh)"
```

Check that the installation went smoothly by looking for clean output from the following command:

```bash
dfx --version
```

## Deployment

To create and deploy a simple sample application called `hello_world`:

```bash
# create a new default project called hello_world
npx azle new hello_world --http-server --experimental
cd hello_world
```

```bash
# install all npm dependencies including azle
npm install
```

```bash
# start up a local ICP replica
dfx start --clean
```

In a separate terminal in the `hello_world` directory:

```bash
# deploy your canister
dfx deploy
```

If you would like your canister to autoreload on file changes:

```bash
AZLE_AUTORELOAD=true dfx deploy
```

View your frontend in a web browser at `http://[canisterId].raw.localhost:4943`.

To obtain your application's [canisterId]:

```bash
dfx canister id backend
```

Communicate with your canister using any HTTP client library, for example using `curl`:

```bash
curl http://[canisterId].raw.localhost:4943/db
curl -X POST -H "Content-Type: application/json" -d "{ \"hello\": \"world\" }" http://[canisterId].raw.localhost:4943/db/update
```

## Testing

If you would like to run the included test suite:

```bash
# start up a local ICP replica
dfx start --clean
```

In a separate terminal in the `hello_world` directory:

```bash
npm test
```
