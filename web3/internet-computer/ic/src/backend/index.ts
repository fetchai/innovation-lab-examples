import { bitcoin_network } from "azle/canisters/management/idl";
import { jsonStringify } from "azle/experimental";
import express, { Request } from "express";

// Dummy values instead of real Bitcoin interactions
const NETWORK: bitcoin_network = { testnet: null };
const DERIVATION_PATH: Uint8Array[] = [];
const KEY_NAME: string = "test_key_1";

const app = express();
app.use(express.json());

/// Dummy: Returns the balance of a given Bitcoin address.
app.get("/", async (req: Request, res) => {
  const welcomeMessage = {
    message: "Welcome to the Dummy Bitcoin Canister API",
  };
  res.json(welcomeMessage);
});

/// Dummy: Returns the balance of a given Bitcoin address.
app.post("/get-balance", async (req: Request, res) => {
  const { address } = req.body;
  const dummyBalance = {
    address: address,
    balance: 0.005, // in BTC
    unit: "BTC",
  };
  res.json(dummyBalance);
});

/// Dummy: Returns the UTXOs of a given Bitcoin address.
app.post("/get-utxos", async (req: Request, res) => {
  const { address } = req.body;
  const dummyUtxos = [
    {
      txid: "dummy-txid-1",
      vout: 0,
      value: 25000,
      confirmations: 5,
    },
    {
      txid: "dummy-txid-2",
      vout: 1,
      value: 50000,
      confirmations: 3,
    },
  ];
  res.json(dummyUtxos);
});

/// Dummy: Returns the 100 fee percentiles measured in millisatoshi/byte.
app.post("/get-current-fee-percentiles", async (_req, res) => {
  const dummyFees = Array.from({ length: 100 }, (_, i) => 100 + i); // Example: [100, 101, ..., 199]
  res.json(dummyFees);
});

/// Dummy: Returns the P2PKH address of this canister.
app.post("/get-p2pkh-address", async (_req, res) => {
  const dummyAddress = "tb1qdummyaddressxyz1234567890";
  res.json({ address: dummyAddress });
});

/// Dummy: Sends satoshis from this canister to a specified address.
app.post("/send", async (req, res) => {
  try {
    const { destinationAddress, amountInSatoshi } = req.body;

    const dummyTxId = "dummy-txid-sent-1234567890";
    const response = {
      success: true,
      destination: destinationAddress,
      amount: amountInSatoshi,
      txId: dummyTxId,
    };
    res.json(response);
  } catch (error: any) {
    res.status(500).json({
      success: false,
      error: {
        code: "DUMMY_ERROR",
        message: "This is a dummy error response",
        details: null,
      },
    });
  }
});

/// Dummy test endpoint
app.post("/dummy-test", (_req, res) => {
  const dummyResponse = {
    status: "success",
    data: {
      message: "This is a dummy response",
      timestamp: new Date().toISOString(),
      testData: {
        id: 1,
        name: "Test Bitcoin Data",
        value: 0.001,
        isTest: true,
      },
    },
  };
  res.json(dummyResponse);
});

app.use(express.static("/dist"));

app.listen();

export function determineKeyName(network: bitcoin_network): string {
  return "test_key_1"; // always return dummy key
}

export function determineNetwork(
  networkName?: string,
): bitcoin_network | undefined {
  return { testnet: null }; // always return dummy network
}
