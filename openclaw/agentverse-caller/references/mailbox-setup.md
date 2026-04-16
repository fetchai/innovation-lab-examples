# Fetch Agents Setup

## Install dependencies

```bash
pip install uagents uagents-core
```

## First-time mailbox setup

The `call.py` script needs an Agentverse mailbox to receive responses from remote agents. This is a one-time setup:

1. Run the call script once:
   ```bash
   python3 scripts/call.py stats "1, 2, 3"
   ```

2. In the logs, find the **Agent Inspector URL**:
   ```
   Agent inspector available at https://agentverse.ai/inspect/?uri=...
   ```

3. Open that URL in your browser

4. Click **Connect** > **Mailbox**

5. The terminal should confirm: `Successfully registered as mailbox agent`

After this, all future calls will work automatically. The agent identity is tied to the seed, so the mailbox persists across runs.

## Custom seed

If you want a different agent identity:

```bash
python3 scripts/call.py stats "1, 2, 3" --seed "my-custom-seed-phrase"
```

Then repeat the mailbox setup for the new identity.

## Testnet

All agents run on the Fetch.ai Dorado testnet. The caller agent is auto-funded for Almanac registration. No FET tokens needed for sending/receiving messages.

## Troubleshooting

- **Port conflict**: The script picks a random port (9100-9999). If it fails, just retry.
- **Timeout**: If you get no response, the mailbox may not be set up. Follow the steps above.
- **"Agent mailbox not found"**: This warning means the mailbox hasn't been created yet. Visit the inspector URL to set it up.
