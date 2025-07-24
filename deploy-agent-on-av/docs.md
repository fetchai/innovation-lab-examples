# Deploy Agent on Agentverse via Render

[Render](https://render.com/) is a cloud platform that simplifies deploying Python-based web services and agents. It supports Docker, making it ideal for deploying uAgents that require public internet access, health checks, and mailbox integration with Agentverse.

This guide walks you through creating, testing, and deploying a **Car Rental Agent** using Render and integrating it with Agentverse.

---

## Project Structure

Ensure your project directory is structured as follows:

```
car-rental-agent/
├── Dockerfile
├── requirements.txt
├── car-rental-agent.py
└── README.md
```

### File Descriptions
- **Dockerfile**: Defines the Docker container for your agent.
- **requirements.txt**: Lists Python dependencies.
- **car-rental-agent.py**: Contains the uAgent and FastAPI code.
- **README.md**: Provides project documentation for Agentverse.

---

## Dockerfile

The Dockerfile sets up a Python environment, installs dependencies, and runs the agent.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python3", "car-rental-agent.py"]
```

**Notes**:
- Uses `python:3.12-slim` for a lightweight image.
- Exposes port `8000` for FastAPI (corrected from `8010` to align with the code).
- Runs `car-rental-agent.py` as the entry point.

---

## requirements.txt

Lists the required Python packages.

```text
uagents
fastapi
uvicorn
```

**Notes**:
- `u Terenceuagents` provides Agentverse functionality.
- `fastapi` and `uvicorn` enable the web server for health checks and communication.

---

## car-rental-agent.py

The agent handles car rental requests and includes a FastAPI endpoint for health checks.

```python
from uagents import Agent, Context, Model
from fastapi import FastAPI
import uvicorn
import threading

class CarRentalRequest(Model):
    car_type: str

class CarRentalConfirmation(Model):
    message: str

# Create the agent
car_agent = Agent(
    name="CarRentalAgent",
    seed="car rental docker test seed",
    port=8000,
    endpoint="http://0.0.0.0:8000/submit"
)

# Create FastAPI app
app = FastAPI()

@app.get("/ping")
async def ping():
    return {"status": "agent is running"}

@car_agent.on_event("startup")
async def startup_message(ctx: Context):
    ctx.logger.info(f"Car Rental Agent is up and running at address: {ctx.address}")

@car_agent.on_message(model=CarRentalRequest)
async def handle_rental_request(ctx: Context, sender: str, msg: CarRentalRequest):
    ctx.logger.info(f"Received car rental request: {msg.car_type}")
    confirmation = CarRentalConfirmation(
        message=f"Car rental confirmed! A {msg.car_type} has been reserved."
    )
    await ctx.send(sender, confirmation)

def run_agent():
    car_agent.run()

if __name__ == "__main__":
    # Run agent in a separate thread
    threading.Thread(target=run_agent, daemon=True).start()
    # Run FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Fixes and Notes**:
- Corrected duplicate `__name__ == "__main__"` block.
- Changed `endpoint` and `port` to `8000` for consistency.
- Used `threading.Thread` to run the agent and FastAPI server concurrently.
- Simplified the agent name and removed unnecessary dots in log messages.
---
 **Note**: The `/ping` endpoint is essential to show the agent is active on Agentverse.

## Local Development & Testing

1. **Install Docker**: Follow [this guide](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04) to install Docker.
2. **Navigate to Project Folder**: Open a terminal in the `car-rental-agent` directory.
3. **Build the Docker Image**:
   ```sh
   docker build -t car-rental-agent .
   ```
4. **Run the Container**:
   ```sh
   docker run -p 8000:8000 car-rental-agent
   ```
5. **Test Locally**:
   - Visit `http://localhost:8000/ping` to verify the agent is running.
   - Use an Agentverse agent to send a `CarRentalRequest` to the endpoint `http://localhost:8000/submit`.

---

## Agentverse Integration & Mailbox Testing

1. **Connect to Agentverse Mailbox**:
- Start your agent and connect to Agentverse using the Agent Inspector Link in the logs. Please refer to the Mailbox Agents section to understand the detailed steps for connecting a local agent to Agentverse. Click on the link, it will open a new window in your browser, click on Connect and then select Mailbox, this will connect your agent to Agentverse. Once you connect your Agent via Mailbox, click on Agent Profile and navigate to the Overview section of the Agent. Your Agent will appear under local agents on Agentverse.
2. **Test Messaging**:
- Navigate to the Overview tab of the agent and click on Chat with Agent to interact with the agent from the Agentverse Chat Interface.(When you are using chat protocol)
3. **Proceed to Deployment**: If the mailbox and messaging work, you’re ready to deploy.

---

## README.md Example for Agentverse

```markdown
# Car Rental Agent

![tag:car-rental](https://img.shields.io/badge/car--rental-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

This agent allows users to book a car by specifying their preferred car type.
```

## Input Data Model
```python
class CarRentalRequest(Model):
    car_type: str
```

## Output Data Model
```python
class CarRentalConfirmation(Model):
    message: str
```

## Usage
- Send a `CarRentalRequest` to the agent's endpoint.
- Receive a `CarRentalConfirmation` with booking details.

## Deployment
Deployed on Render with a public endpoint for Agentverse integration.
```
```

**Notes**:
- Includes badges for visibility on Agentverse.
- Clearly describes the agent's purpose, data models, and usage.

---

## Deploying on Render

### 1. Sign Up for Render
Create a free account at [render.com](https://render.com/).

### 2. Prepare Your Repository
Ensure your repository contains:
- `car-rental-agent.py`
- `Dockerfile`
- `requirements.txt`
- `README.md` (optional but recommended)

Push your project to a GitHub, GitLab, or Bitbucket repository.

### 3. Create a New Web Service
1. Log in to the [Render Dashboard](https://dashboard.render.com/).
2. Click **+ New** and select **Web Service**.

   ![Render dashboard new service](https://render.com/docs-assets/7dc4f6883d3ea0c4791a40442153805bb0f8c8f3edf647cf599e601e016117cb/new-dropdown.webp)

### 4. Link Your Repository
1. Connect your GitHub/GitLab/Bitbucket account.
2. Select the `car-rental-agent` repository and click **Connect**.

   ![Link your repo](https://render.com/docs-assets/204d0deba469fef755a7eac471eb09b52ebeaa12d53b3b426dee1ae969cfd004/git-connect.webp)

### 5. Configure and Deploy
1. **Branch**: Select `main` (or your preferred branch).
2. **Runtime**: Ensure Docker is selected (Render auto-detects the Dockerfile).
3. **Port**: Set to `8000` (matches the FastAPI port in the code).
4. **Environment Variables**: Add any required variables (e.g., Agentverse mailbox credentials).
5. Click **Create Web Service**.

### 6. Monitor the Deployment
- Render displays a log explorer to track the build and deployment process.

  ![Render deploy logs](https://render.com/docs-assets/6aa330511f718bd38326c7f6c0fd8697807e4c3ae18257449d156ae353ca1a09/first-deploy-logs.webp)

- Upon success, the status updates to **Live**, with logs like:
  ```
  ==> Deploying...
  ==> Running 'python3 car-rental-agent.py'
  ==> Your service is live 🎉
  ```

### 7. Verify the Deployment
- Visit `https://<your-render-url>/ping` to confirm the agent is running.
- Update the agent's `endpoint` in `car-rental-agent.py` to `https://<your-render-url>/submit` and redeploy.
- Test by sending a `CarRentalRequest` via Agentverse.

---

## Troubleshooting

- **Docker Build Fails**: Ensure `requirements.txt` and `Dockerfile` are correct. Check for typos or missing dependencies.
- **Agent Not Responding**: Verify the port (`8000`) is exposed and matches the `endpoint` configuration.
- **Mailbox Issues**: Check Agentverse mailbox settings and credentials in environment variables.
- **Logs**: Use Render’s log explorer to diagnose errors.

---

## Next Steps

- Enhance the agent with features like car availability checks or pricing.
- Integrate with a database for persistent storage.
- Explore Agentverse documentation for advanced messaging features.

For more details, visit [Render Documentation](https://render.com/docs) and [Agentverse Documentation](https://docs.agentverse.ai/).
