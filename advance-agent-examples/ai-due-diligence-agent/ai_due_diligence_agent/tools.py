"""Custom tools for the Due Diligence Pipeline.

Provides HTML report generation, financial charts, and infographic creation.
"""

import logging
from datetime import timedelta
from google.adk.tools.tool_context import ToolContext
from google.genai import types, Client
from typing import Any
from google.cloud import storage

logger = logging.getLogger("DueDiligencePipeline")


def generate_signed_gcs_url(
    artifact_version,
    expires_in_minutes: int = 300,
) -> str:
    """
    Generate a time-limited public URL for a GCS object.
    """
    gs_uri = artifact_version.canonical_uri
    _, _, rest = gs_uri.partition("gs://")
    bucket_name, _, object_path = rest.partition("/")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)

    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expires_in_minutes),
        method="GET",
    )
    return url


async def generate_financial_chart(
    company_name: str,
    current_arr: float,
    bear_rates: str,
    base_rates: str,
    bull_rates: str,
    tool_context: ToolContext
) -> dict[str, Any]:
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use("Agg")
        import io
        from datetime import datetime

        bear = [float(x.strip()) for x in bear_rates.split(",")]
        base = [float(x.strip()) for x in base_rates.split(",")]
        bull = [float(x.strip()) for x in bull_rates.split(",")]

        years = list(range(2025, 2025 + len(base) + 1))

        def project(start, rates):
            out = [start]
            for r in rates:
                out.append(out[-1] * r)
            return out

        bear_arr = project(current_arr, bear)
        base_arr = project(current_arr, base)
        bull_arr = project(current_arr, bull)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(years, bear_arr, label="Bear", color="#dc2626")
        ax.plot(years, base_arr, label="Base", color="#1a365d", linewidth=3)
        ax.plot(years, bull_arr, label="Bull", color="#16a34a")
        ax.fill_between(years, bear_arr, bull_arr, alpha=0.1)

        ax.set_title(f"{company_name} – Revenue Projections")
        ax.set_xlabel("Year")
        ax.set_ylabel("ARR ($M)")
        ax.legend()
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        plt.close()
        buf.seek(0)

        artifact_name = f"revenue_chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        artifact = types.Part.from_bytes(
            data=buf.read(), mime_type="image/png")

        version = await tool_context.save_artifact(
            filename=artifact_name,
            artifact=artifact,
        )

        av = await tool_context.get_artifact_version(
            filename=artifact_name,
            version=version,
        )

        result = {
            "status": "success",
            "artifact": artifact_name,
            "version": version,
            "public_link": generate_signed_gcs_url(av),
        }
        print(result)
        return result

    except Exception as e:
        logger.exception("Chart generation failed")
        return {"status": "error", "message": str(e)}


async def generate_html_report(
    report_data: str,
    tool_context: ToolContext
) -> dict[str, Any]:
    from datetime import datetime
    from google.genai import Client, types
    import json

    try:
        client = Client()

        # 1️⃣ Ask Gemini for STRUCTURED CONTENT ONLY (no HTML)
        prompt = f"""
You are an investment analyst.

Convert the following investor memo into structured JSON with these keys:
- executive_summary
- company_overview
- market_opportunity
- financial_analysis
- risk_assessment
- investment_recommendation

Rules:
- Plain text only
- Use paragraphs and bullet points
- NO HTML
- NO markdown
- Valid JSON only

INVESTOR MEMO:
{report_data}
"""

        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )

        structured = json.loads(response.text)

        # 2️⃣ Professional locked HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Investment Memorandum</title>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<style>
body {{
  font-family: Inter, system-ui, -apple-system;
  background: #f9fafb;
  margin: 0;
  color: #111827;
}}

.page {{
  max-width: 900px;
  margin: 40px auto;
  background: #ffffff;
  padding: 64px;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.08);
}}

h1 {{
  font-size: 36px;
  margin-bottom: 8px;
}}

.subtitle {{
  color: #6b7280;
  margin-bottom: 40px;
}}

.section {{
  margin-bottom: 48px;
}}

.section h2 {{
  font-size: 22px;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 6px;
}}

.highlight {{
  background: #f1f5f9;
  border-left: 4px solid #0f172a;
  padding: 16px;
  margin-top: 16px;
}}

footer {{
  text-align: center;
  font-size: 13px;
  color: #6b7280;
  margin-top: 64px;
}}
</style>
</head>

<body>
<div class="page">
  <h1>Investment Memorandum</h1>
  <div class="subtitle">Confidential — Internal Use Only</div>

  <div class="section">
    <h2>Executive Summary</h2>
    <p>{structured["executive_summary"]}</p>
  </div>

  <div class="section">
    <h2>Company Overview</h2>
    <p>{structured["company_overview"]}</p>
  </div>

  <div class="section">
    <h2>Market Opportunity</h2>
    <p>{structured["market_opportunity"]}</p>
  </div>

  <div class="section">
    <h2>Financial Analysis</h2>
    <p>{structured["financial_analysis"]}</p>
  </div>

  <div class="section">
    <h2>Risk Assessment</h2>
    <p>{structured["risk_assessment"]}</p>
  </div>

  <div class="section">
    <h2>Investment Recommendation</h2>
    <div class="highlight">
      {structured["investment_recommendation"]}
    </div>
  </div>

  <footer>
    Generated on {datetime.utcnow().strftime("%d %b %Y")}
  </footer>
</div>
</body>
</html>
"""

        # 3️⃣ Save artifact
        artifact_name = f"investment_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"

        artifact = types.Part.from_bytes(
            data=html.encode("utf-8"),
            mime_type="text/html",
        )

        version = await tool_context.save_artifact(
            filename=artifact_name,
            artifact=artifact,
        )

        av = await tool_context.get_artifact_version(
            filename=artifact_name,
            version=version,
        )

        return {
            "status": "success",
            "artifact": artifact_name,
            "version": version,
            "public_link": generate_signed_gcs_url(av),
        }

    except Exception as e:
        logger.exception("HTML report generation failed")
        return {"status": "error", "message": str(e)}


async def generate_infographic(
    data_summary: str,
    tool_context: ToolContext
) -> dict[str, Any]:
    from datetime import datetime

    try:
        client = Client()
        response = await client.aio.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=data_summary,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                artifact_name = f"infographic_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                artifact = types.Part.from_bytes(
                    data=part.inline_data.data,
                    mime_type=part.inline_data.mime_type,
                )

                version = await tool_context.save_artifact(
                    filename=artifact_name,
                    artifact=artifact,
                )

                av = await tool_context.get_artifact_version(
                    filename=artifact_name,
                    version=version,
                )

                return {
                    "status": "success",
                    "artifact": artifact_name,
                    "version": version,
                    "public_link": generate_signed_gcs_url(av),
                }

        return {"status": "partial", "message": "No image returned"}

    except Exception as e:
        logger.exception("Infographic generation failed")
        return {"status": "error", "message": str(e)}
