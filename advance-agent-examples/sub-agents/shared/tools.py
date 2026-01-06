"""Custom tools for the Due Diligence Pipeline.

Provides HTML report generation, financial charts, and infographic creation.
"""

import logging
from datetime import timedelta
from google.adk.tools.tool_context import ToolContext
from google.genai import types, Client
from typing import Any
from google.cloud import storage
from google.adk.tools.google_search_tool import google_search

logger = logging.getLogger("DueDiligencePipeline")

def generate_signed_gcs_url(
    artifact_version: Any,
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
        artifact = types.Part.from_bytes(data=buf.read(), mime_type="image/png")

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
        return result

    except Exception as e:
        logger.exception("Chart generation failed")
        return {"status": "error", "message": str(e)}

async def generate_html_report(
    report_data: str,
    tool_context: ToolContext
) -> dict[str, Any]:
    from datetime import datetime

    try:
        client = Client()
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=report_data,
        )

        html = response.text.strip("` \n")
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

        result = {
            "status": "success",
            "artifact": artifact_name,
            "version": version,
            "public_link": generate_signed_gcs_url(av),
        }
        return result

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


__all__ = [
    "generate_financial_chart",
    "generate_html_report",
    "generate_infographic",
    "google_search",
]