# Blood Report Analysis Agent

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:crewai](https://img.shields.io/badge/crewai-D9644E)

The **Blood Report Analysis Agent** is designed to analyze blood test reports from PDF files hosted on Google Drive, powered by **CrewAI** and the **uAgents Adapter**. It delivers a comprehensive summary of key health indicators and tailored health recommendations in a Markdown-formatted console output.

---

## 🧩 Overview

### 🔍 Features

- **PDF Processing**: Downloads and extracts text from blood report PDFs.
- **Health Analysis**: Summarizes key indicators (e.g., uric acid, GGTP, electrolytes) with significance and reference ranges.
- **Recommendations**:  
  Provides detailed advice for each indicator, including:
  - *What It Means*
  - *How to Control It*
  - *Dietary Tips*
  - *Exercise Routines*
  - *Potential Medications*
  - *Lifestyle Changes*  
  All supported with **source citations**.
- **Multi-User Support**: Clears previous data to process new PDFs for each user.
- **Disclaimer**: Includes standard disclaimers that the output is not a substitute for professional medical advice.

👉 A "Go to Chat" button is provided to send requests to the main agent.

---

## 📥 Example Request

Send a Drive link like the following:

```
https://drive.google.com/file/d/1LQYFaXJ9sFTYi4pW4pis5Ln-xzp0jRLq/view?usp=sharing
```

---

## ✅ Response

```
Blood Report Analysis Completed ✅

📋 Summary: Blood Test Report Analysis

👤 Patient Information:
- Age: 30 years
- Gender: Male
- Report Date: 14/05/2023
- Lab: LPL - National Reference Lab
```