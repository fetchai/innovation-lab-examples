#!/bin/bash
# The Admin Layer: Model Armor Template
# While developers write Python, Admins configure Model Armor to sanitize data globally.

# Configuration
LOCATION="us-central1"  # Update with your location
PROJECT_ID="fetch-ai-innovation-lab"  # Update with your Google Cloud project ID
LOCATION_ID="us-central1"  # Update with your location ID
TEMPLATE_ID="security_guardrails_template"  # Update with your template ID

export TEMPLATE_CONFIG='{
  "filterConfig": {
    "raiSettings": {
      "raiFilters": [{
        "filterType": "HATE_SPEECH",
        "confidenceLevel": "MEDIUM_AND_ABOVE"
      }, {
        "filterType": "HARASSMENT",
        "confidenceLevel": "HIGH"
      }]
    },
    "piAndJailbreakFilterSettings": {
      "filterEnforcement": "ENABLED",
      "confidenceLevel": "LOW_AND_ABOVE"
    }
  },
  "templateMetadata": {
    "multiLanguageDetection": {
      "enableMultiLanguageDetection": true
    }
  }
}'

curl -X POST \
  -d "$TEMPLATE_CONFIG" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://modelarmor.${LOCATION}.rep.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION_ID}/templates?template_id=${TEMPLATE_ID}"

