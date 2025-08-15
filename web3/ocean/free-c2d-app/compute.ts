import "dotenv/config";
import fs from "fs";
import { homedir } from "os";
import crypto from "crypto-js";
import express from "express";
import cors from "cors";

import { ethers, JsonRpcProvider, Signer, toBeHex } from "ethers";

// ocean.js v5 surface (mapped from test's ../../src/index.js to package import)
import {
	ProviderInstance,
	Aquarius,
	NftFactory,
	Datatoken,
	Nft,
	ZERO_ADDRESS,
	transfer,
	sleep,
	approveWei,
	ProviderComputeInitialize,
	ConsumeMarketFee,
	ComputeAlgorithm,
	ComputeAsset,
	Config,
	Files,
	NftCreateData,
	DatatokenCreateParams,
	sendTx,
	configHelperNetworks,
	ConfigHelper,
	getEventFromTx,
	amountToUnits,
	isDefined,
} from "@oceanprotocol/lib";
import { DDO } from "@oceanprotocol/ddo-js";

const { SHA256 } = crypto;

// Express app setup
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Global variables for compute job tracking
let currentComputeJobId = "";
let currentAgreementId = "";
let isComputeJobRunning = false;
let computeJobResult: any = null;
let computeJobError: string | null = null;

// Ocean Protocol variables
let config: Config;
let aquariusInstance: Aquarius;
let datatoken: Datatoken;
let providerUrl: string;
let publisherAccount: Signer;
let consumerAccount: Signer;
let addresses: any;
let computeEnvs: any;
let datasetId = "";
let algorithmId = "";
let resolvedDatasetDdo: DDO;
let resolvedAlgorithmDdo: DDO;
let hasFreeComputeSupport = true;

// -------- Constants from the test (same assets/DDOs) -------- //
const DATASET_ASSET_URL: Files = {
	datatokenAddress: "0x0",
	nftAddress: "0x0",
	files: [
		{
			type: "url",
			url: "https://raw.githubusercontent.com/kshipra-fetch/test-repo/main/demographics-data.csv",
			method: "GET",
		},
	],
};

const ALGORITHM_ASSET_URL: Files = {
	datatokenAddress: "0x0",
	nftAddress: "0x0",
	files: [
		{
			type: "url",
			url: "https://raw.githubusercontent.com/kshipra-fetch/test-repo/main/demographics-algorithm.py",
			method: "GET",
		},
	],
};

const DATASET_DDO: DDO = {
	"@context": ["https://w3id.org/did/v1"],
	id: "did:op:placeholder",
	version: "4.1.0",
	chainId: 8996,
	nftAddress: "0x0",
	metadata: {
		created: "2021-12-20T14:35:20Z",
		updated: "2021-12-20T14:35:20Z",
		type: "dataset",
		name: "dataset-name",
		description: "Ocean protocol test dataset description",
		author: "oceanprotocol-team",
		license: "https://market.oceanprotocol.com/terms",
		additionalInformation: { termsAndConditions: true },
	},
	services: [
		{
			id: "compute-svc",
			type: "compute",
			files: "",
			datatokenAddress: "0x0",
			serviceEndpoint: "http://127.0.0.1:8001",
			timeout: 300,
			compute: {
				publisherTrustedAlgorithmPublishers: ["*"] as any,
				publisherTrustedAlgorithms: [
					{ did: "*", filesChecksum: "*", containerSectionChecksum: "*" },
				] as any,
				allowRawAlgorithm: false,
				allowNetworkAccess: true,
			},
		},
	],
};

const ALGORITHM_DDO: DDO = {
	"@context": ["https://w3id.org/did/v1"],
	id: "did:op:placeholder",
	version: "4.1.0",
	chainId: 8996,
	nftAddress: "0x0",
	metadata: {
		created: "2021-12-20T14:35:20Z",
		updated: "2021-12-20T14:35:20Z",
		type: "algorithm",
		name: "algorithm-name",
		description: "Ocean protocol test algorithm description",
		author: "oceanprotocol-team",
		license: "https://market.oceanprotocol.com/terms",
		additionalInformation: { termsAndConditions: true },
		algorithm: {
			language: "Python",
			version: "1.0.0",
			container: {
				entrypoint: "python $ALGO",
				image: "python",
				tag: "3.9-alpine",
				checksum: "sha256:372f3cfc1738ed91b64c7d36a7a02d5c3468ec1f60c906872c3fd346dda8cbbb",
			},
		},
	},
	services: [
		{
			id: "access-svc",
			type: "access",
			files: "",
			datatokenAddress: "0x0",
			serviceEndpoint: "http://127.0.0.1:8001",
			timeout: 300,
		},
	],
};

// -------- Core Ocean Protocol Logic (unchanged) -------- //
async function createAssetHelper(
	name: string,
	symbol: string,
	owner: Signer,
	assetUrl: Files,
	ddo: DDO,
	providerUrlLocal: string
) {
	const { chainId } = await owner.provider!.getNetwork();
	const nft = new Nft(owner, Number(chainId));
	const nftFactory = new NftFactory(
		addresses.ERC721Factory,
		owner,
		Number(chainId)
	);
	ddo.chainId = Number(chainId);

	const nftParamsAsset: NftCreateData = {
		name,
		symbol,
		templateIndex: 1,
		tokenURI: "aaa",
		transferable: true,
		owner: await owner.getAddress(),
	};

	const datatokenParams: DatatokenCreateParams = {
		templateIndex: 1,
		cap: "100000",
		feeAmount: "0",
		paymentCollector: ZERO_ADDRESS,
		feeToken: ZERO_ADDRESS,
		minter: await owner.getAddress(),
		mpFeeAddress: ZERO_ADDRESS,
	};

	const bundleNFT = await nftFactory.createNftWithDatatoken(
		nftParamsAsset,
		datatokenParams
	);
	const trxReceipt = await bundleNFT.wait();

	const nftCreatedEvent = getEventFromTx(trxReceipt, "NFTCreated");
	const tokenCreatedEvent = getEventFromTx(trxReceipt, "TokenCreated");
	const nftAddress = nftCreatedEvent.args.newTokenAddress;
	const datatokenAddressAsset = tokenCreatedEvent.args.newTokenAddress;

	// encrypt files & DDO with Provider
	assetUrl.datatokenAddress = datatokenAddressAsset;
	assetUrl.nftAddress = nftAddress;
	ddo.services[0].files = await ProviderInstance.encrypt(
		assetUrl,
		Number(chainId),
		providerUrlLocal
	);
	ddo.services[0].datatokenAddress = datatokenAddressAsset;
	ddo.services[0].serviceEndpoint = providerUrlLocal;
	ddo.nftAddress = nftAddress;
	ddo.id =
		"did:op:" + SHA256(ethers.getAddress(nftAddress) + chainId.toString(10));

	const encryptedResponse = await ProviderInstance.encrypt(
		ddo,
		Number(chainId),
		providerUrlLocal
	);
	const validateResult = await aquariusInstance.validate(
		ddo,
		owner,
		providerUrlLocal
	);

	await nft.setMetadata(
		nftAddress,
		await owner.getAddress(),
		0,
		providerUrlLocal,
		"",
		toBeHex(2),
		encryptedResponse,
		validateResult.hash
	);

	return ddo.id;
}

// -------- HTTP Endpoints -------- //
app.get('/health', (req, res) => {
	res.json({ status: 'OK', message: 'Compute service is running' });
});

app.post('/compute/start', async (req, res) => {
	try {
		if (isComputeJobRunning) {
			return res.status(400).json({ 
				error: 'Compute job already running', 
				jobId: currentComputeJobId 
			});
		}

		// Initialize the compute environment if not already done
		if (!config || !aquariusInstance || !datatoken) {
			await initializeComputeEnvironment();
		}

		// Start the compute job
		isComputeJobRunning = true;
		computeJobError = null;
		computeJobResult = null;

		// Start the compute job and wait for the job ID
		const jobId = await startComputeJobAndGetId();

		res.json({ 
			message: 'Compute job started successfully',
			jobId: jobId,
			status: 'running'
		});
	} catch (error) {
		isComputeJobRunning = false;
		console.error('Error starting compute job:', error);
		res.status(500).json({ 
			error: 'Failed to start compute job',
			details: error instanceof Error ? error.message : 'Unknown error'
		});
	}
});

app.get('/compute/status', (req, res) => {
	if (!isComputeJobRunning && !computeJobResult && !computeJobError) {
		return res.json({ 
			status: 'idle',
			message: 'No compute job has been started'
		});
	}

	if (computeJobError) {
		return res.json({
			status: 'error',
			jobId: currentComputeJobId,
			error: computeJobError
		});
	}

	if (computeJobResult) {
		return res.json({
			status: 'completed',
			jobId: currentComputeJobId,
			result: computeJobResult
		});
	}

	res.json({
		status: 'running',
		jobId: currentComputeJobId,
		message: 'Compute job is still running'
	});
});

app.get('/compute/result', async (req, res) => {
	if (!computeJobResult) {
		return res.status(404).json({ 
			error: 'No compute result available. Check status first.' 
		});
	}

	res.json({
		jobId: currentComputeJobId,
		result: computeJobResult
	});
});

app.post('/compute/reset', (req, res) => {
	isComputeJobRunning = false;
	currentComputeJobId = "";
	currentAgreementId = "";
	computeJobResult = null;
	computeJobError = null;
	
	res.json({ message: 'Compute job state reset successfully' });
});

// -------- Core Ocean Protocol Functions -------- //
async function initializeComputeEnvironment() {
	// --- 1. config & accounts ---
	const provider = new JsonRpcProvider(process.env.RPC);
	publisherAccount = (await provider.getSigner(0)) as Signer;
	consumerAccount = (await provider.getSigner(1)) as Signer;

	const cfg = new ConfigHelper().getConfig(
		parseInt(String((await publisherAccount.provider!.getNetwork()).chainId))
	);
	if (process.env.NODE_URL) cfg.oceanNodeUri = process.env.NODE_URL;
	aquariusInstance = new Aquarius(cfg.oceanNodeUri);
	providerUrl = cfg.oceanNodeUri;
	config = cfg;

	addresses = JSON.parse(
		fs.readFileSync(
			process.env.ADDRESS_FILE ||
				`${homedir}/.ocean/ocean-contracts/artifacts/address.json`,
			"utf8"
		)
	).development;

	console.log(`Indexer URL: ${config.oceanNodeUri}`);
	console.log(`Provider URL: ${providerUrl}`);
	console.log(`Deployed contracts: ${addresses?.ERC721Factory ? "loaded" : "missing"}`);
	console.log(`Publisher: ${await publisherAccount.getAddress()}`);
	console.log(`Consumer: ${await consumerAccount.getAddress()}`);

	// --- 2. Mint OCEAN to publisher & transfer to consumer ---
	const minAbi = [
		{
			constant: false,
			inputs: [
				{ name: "to", type: "address" },
				{ name: "value", type: "uint256" },
			],
			name: "mint",
			outputs: [{ name: "", type: "bool" }],
			payable: false,
			stateMutability: "nonpayable",
			type: "function",
		},
	];
	const tokenContract = new ethers.Contract(
		addresses.Ocean,
		minAbi,
		publisherAccount
	);
	const estGasPublisher = await tokenContract.mint.estimateGas(
		await publisherAccount.getAddress(),
		amountToUnits(null, null, "1000", 18)
	);
	await sendTx(
		estGasPublisher,
		publisherAccount,
		1,
		tokenContract.mint,
		await publisherAccount.getAddress(),
		amountToUnits(null, null, "1000", 18)
	);

	await transfer(
		publisherAccount,
		config,
		addresses.Ocean,
		await consumerAccount.getAddress(),
		"100"
	);

	// --- 3. Publish dataset & algorithm ---
	datasetId = await createAssetHelper(
		"D1Min",
		"D1M",
		publisherAccount,
		DATASET_ASSET_URL,
		DATASET_DDO,
		providerUrl
	);
	console.log("dataset id:", datasetId);

	algorithmId = await createAssetHelper(
		"A1Min",
		"A1M",
		publisherAccount,
		ALGORITHM_ASSET_URL,
		ALGORITHM_DDO,
		providerUrl
	);
	console.log("algorithm id:", algorithmId);

	// --- 4. Resolve assets ---
	resolvedDatasetDdo = await aquariusInstance.waitForIndexer(datasetId);
	resolvedAlgorithmDdo = await aquariusInstance.waitForIndexer(algorithmId);

	// --- 5. Mint datatokens to consumer ---
	const { chainId } = await publisherAccount.provider!.getNetwork();
	datatoken = new Datatoken(publisherAccount, Number(chainId));
	await datatoken.mint(
		resolvedDatasetDdo.services[0].datatokenAddress,
		await publisherAccount.getAddress(),
		"10",
		await consumerAccount.getAddress()
	);
	await datatoken.mint(
		resolvedAlgorithmDdo.services[0].datatokenAddress,
		await publisherAccount.getAddress(),
		"10",
		await consumerAccount.getAddress()
	);

	// --- 6. Get compute environments ---
	computeEnvs = await ProviderInstance.getComputeEnvironments(providerUrl);
	const freeEnv = computeEnvs.find((ce: any) => isDefined(ce.free));
	if (!freeEnv) {
		hasFreeComputeSupport = false;
		throw new Error("No free compute environment found on your local node.");
	}
	console.log("Free compute environment =", freeEnv);
}

async function startComputeJobAndGetId(): Promise<string> {
	// --- Start FREE compute job ---
	const assets: ComputeAsset[] = [
		{
			documentId: resolvedDatasetDdo.id,
			serviceId: resolvedDatasetDdo.services[0].id,
		},
	];
	const algo: ComputeAlgorithm = {
		documentId: resolvedAlgorithmDdo.id,
		serviceId: resolvedAlgorithmDdo.services[0].id,
		meta: (resolvedAlgorithmDdo as any).metadata.algorithm,
	};

	const freeEnv = computeEnvs.find((ce: any) => isDefined(ce.free));
	const computeJobs = await ProviderInstance.freeComputeStart(
		providerUrl,
		consumerAccount,
		freeEnv.id,
		assets,
		algo
	);
	
	const jobId = computeJobs[0].jobId;
	const agreementId = computeJobs[0].agreementId;
	
	// Set the global variables
	currentComputeJobId = jobId;
	currentAgreementId = agreementId;
	
	console.log("Started FREE compute job:", jobId);
	
	// Start the background polling process
	startComputeJobPolling(jobId, agreementId);
	
	return jobId;
}

async function startComputeJobPolling(jobId: string, agreementId: string) {
	try {
		// --- Poll for job completion ---
		console.log("Polling for job completion...");
		let attempts = 0;
		const maxAttempts = 30; // 5 minutes max

		while (attempts < maxAttempts && isComputeJobRunning) {
			await sleep(10000); // Wait 10 seconds

			const status = await ProviderInstance.computeStatus(
				providerUrl,
				await consumerAccount.getAddress(),
				jobId,
				agreementId
			);

			const jobStatus = Array.isArray(status) ? status[0]?.status : status?.status;
			console.log(`Attempt ${attempts + 1}: Job status = ${jobStatus}`);

			if (jobStatus >= 70) {
				console.log("Job completed!");
				const url = await ProviderInstance.getComputeResultUrl(
					providerUrl,
					consumerAccount,
					jobId,
					0
				);
				console.log("Compute results URL:", url);
				
				// Fetch the actual result content immediately before nonce expires
				try {
					const response = await fetch(url);
					if (response.ok) {
						const resultContent = await response.text();
						console.log("Successfully fetched compute result content");
						
						// Store the result with content
						computeJobResult = {
							status: 'completed',
							resultUrl: url,
							resultContent: resultContent,
							jobId: jobId,
							completedAt: new Date().toISOString()
						};
					} else {
						console.error("Failed to fetch result content:", response.status, response.statusText);
						computeJobResult = {
							status: 'completed',
							resultUrl: url,
							resultContent: null,
							jobId: jobId,
							completedAt: new Date().toISOString(),
							error: `Failed to fetch result content: ${response.status} ${response.statusText}`
						};
					}
				} catch (fetchError) {
					console.error("Error fetching result content:", fetchError);
					computeJobResult = {
						status: 'completed',
						resultUrl: url,
						resultContent: null,
						jobId: jobId,
						completedAt: new Date().toISOString(),
						error: `Error fetching result content: ${fetchError instanceof Error ? fetchError.message : 'Unknown error'}`
					};
				}
				break;
			}

			attempts++;
		}

		if (attempts >= maxAttempts) {
			computeJobError = "Job did not complete within timeout period";
			console.log("Job did not complete within timeout period");
		}

		isComputeJobRunning = false;
		console.log("DONE (free compute path).");
	} catch (error) {
		isComputeJobRunning = false;
		computeJobError = error instanceof Error ? error.message : 'Unknown error occurred';
		console.error('Error in compute job:', error);
	}
}

// -------- Start the server -------- //
app.listen(PORT, () => {
	console.log(`🚀 Compute service running on http://localhost:${PORT}`);
	console.log(`📊 Health check: GET http://localhost:${PORT}/health`);
	console.log(`🚀 Start compute: POST http://localhost:${PORT}/compute/start`);
	console.log(`📈 Check status: GET http://localhost:${PORT}/compute/status`);
	console.log(`📄 Get result: GET http://localhost:${PORT}/compute/result`);
	console.log(`🔄 Reset state: POST http://localhost:${PORT}/compute/reset`);
});