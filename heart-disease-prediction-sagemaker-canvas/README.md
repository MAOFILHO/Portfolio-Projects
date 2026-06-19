# ❤️ Heart Disease Risk Prediction Using Amazon SageMaker Canvas
### A No-Code Machine Learning Project on AWS

![AWS](https://img.shields.io/badge/AWS-SageMaker%20Canvas-FF9900?style=flat&logo=amazonaws)
![ML](https://img.shields.io/badge/Type-No--Code%20ML-blue)
![Status](https://img.shields.io/badge/Status-Deployed-brightgreen)

---

## 📌 Project Overview

Heart disease is the world's #1 cause of death. Most healthcare providers already
hold years of patient data (age, cholesterol, blood pressure, ECG readings) but
lack in-house data science teams to extract predictive value from it.

This project demonstrates how a **business analyst with zero ML coding experience**
can build, train, and deploy a production-grade heart disease risk prediction model
entirely through AWS's no-code tooling — no Python, no Jupyter notebooks, no ML
expertise required.

---

## 🎯 Business Problem

| Pain Point | Impact |
|---|---|
| Late diagnoses | Expensive, high-risk interventions |
| Reactive care model | Preventable patient outcomes |
| No in-house data scientists | ML pipelines remain inaccessible |

**Goal:** Identify high-risk patients earlier using existing patient data,
with a model anyone on the clinical or business team can build and maintain.

---

## ☁️ AWS Services Used

| Service | Role |
|---|---|
| **Amazon SageMaker Canvas** | No-code ML model building & deployment |
| **SageMaker Data Wrangler** | Data profiling, quality analysis & preparation |
| **SageMaker Autopilot** | Automated model selection & training |
| **Amazon S3** | Dataset storage |
| **SageMaker Endpoints** | Real-time inference API |

---

## 🏗️ Architecture

Local CSV Dataset
│
▼
Amazon S3 (Raw Storage)
│
▼
SageMaker Data Wrangler ──► Data Quality & Insights Report
│
▼
SageMaker Canvas (No-Code ML)
│
├──► SageMaker Autopilot (Auto Model Training)
│
├──► Model Evaluation (Accuracy, AUC, F1)
│
▼
SageMaker Endpoint (Real-Time Predictions)


---

## 📊 Dataset

- **Source:** Public Heart Disease Dataset
- **Records:** 303 patients
- **Features:** 14 clinical attributes
- **Target Column:** `cp` (chest pain type — proxy for heart disease risk)
- **Missing Values:** 0%
- **Duplicate Rows:** 0.66%

### Key Features

| Feature | Description |
|---|---|
| `age` | Patient age in years |
| `sex` | Biological sex (0 = Female, 1 = Male) |
| `cp` | Chest pain type (0–3) ← **Target** |
| `trestbps` | Resting blood pressure (mmHg) |
| `chol` | Serum cholesterol (mg/dL) |
| `fbs` | Fasting blood sugar > 120 mg/dL |
| `restecg` | Resting ECG results |
| `thalach` | Maximum heart rate achieved |
| `exang` | Exercise-induced angina |

---

## 🔄 ML Pipeline (5 Steps, Zero Code)

**Step 1 — Data Import**
Uploaded `heart-disease-dataset.csv` directly to SageMaker Data Wrangler
via local upload.

**Step 2 — Data Profiling**
Generated a Data Quality & Insights Report:
- ✅ 0% missing values
- ✅ 100% valid records  
- ⚠️ 0.66% duplicate rows identified

**Step 3 — Model Training (Quick Build)**
- Selected target column: `cp` (chest pain / heart disease indicator)
- Model type auto-recommended: **3+ Category Prediction**
- Used **Quick Build** (~15 min) for rapid iteration

**Step 4 — Model Evaluation**

| Metric | Value |
|---|---|
| Accuracy | 56.45% |
| Top Predictive Feature | `target` (19.53% impact) |
| 2nd Top Feature | `exang` (13.33% impact) |
| 3rd Top Feature | `chol` (11.67% impact) |

**Step 5 — Deployment**
- Deployed to SageMaker real-time endpoint
- Instance type: `ml.t2.medium` (×2)
- Status: ✅ **In Service**

---

## 🔮 Prediction Risk Classes

| Class | Meaning |
|---|---|
| `0` | No risk / Healthy |
| `1` | Low risk |
| `2` | Medium risk |
| `3` | High risk |

### Live Test Result
Input: Age = 68, Cholesterol = 250  
**Prediction: Class 2 (Medium Risk) — 51.3% confidence**

---

## 📸 Screenshots


<img width="1664" height="661" alt="01-sagemaker-create-domain" src="https://github.com/user-attachments/assets/2611caa3-b817-4ef6-b493-17581b563cbe" />
<img width="2852" height="1404" alt="02-heart-disease-dataset" src="https://github.com/user-attachments/assets/95e259e4-e97b-4c24-bcba-c8cb64abebc8" />
<img width="1298" height="501" alt="03-sagemaker-canvas" src="https://github.com/user-attachments/assets/ff49a648-38d5-473f-a3f1-f4e30226b102" />
<img width="1669" height="515" alt="04-data-wrangler" src="https://github.com/user-attachments/assets/93899765-10ad-458d-99ae-5e39d8de471d" />
<img width="1661" height="896" alt="05-import-dataset" src="https://github.com/user-attachments/assets/9815f079-2a51-47d3-a761-0a956cc733fc" />
<img width="1561" height="618" alt="06-model-quick-build" src="https://github.com/user-attachments/assets/7a692d20-26de-4300-bed3-8c0ab9f6d012" />
<img width="1561" height="652" alt="07-creating-model" src="https://github.com/user-attachments/assets/862b91b0-363c-4648-93bd-4d7e98a074d0" />
<img width="1562" height="588" alt="08-model-deployed" src="https://github.com/user-attachments/assets/4c5cf7df-f632-4989-9938-a4a409d097a3" />
<img width="1561" height="470" alt="09-prediction-01" src="https://github.com/user-attachments/assets/0b7ac37a-beb7-4502-a08f-2062b07aa305" />
<img width="644" height="482" alt="10-prediction-02" src="https://github.com/user-attachments/assets/d94da754-72e1-4d52-9872-f644ded026b7" />


---

## 💰 Cost

| Resource | Usage | Cost |
|---|---|---|
| SageMaker Canvas (Free Tier) | 160 hrs/month free | $0 |
| Canvas Workspace (beyond free tier) | 2.081 hrs × $1.90/hr | $3.95 |
| **Total** | | **~$3.95** |

> ⚠️ **Important:** Always delete SageMaker endpoints, models, and domains
> after completing the project to avoid ongoing charges.

---

## 🧠 Key Takeaways

- **No-code ML is production-ready.** SageMaker Canvas delivers real
  classification models without a single line of code.
- **Data quality is ML quality.** Data Wrangler's automated profiling
  identified issues before they could affect model training.
- **The barrier to healthcare AI is lower than ever.** A business analyst
  can own this entire pipeline end-to-end.
- **AWS democratizes ML.** What used to require a data science team
  now runs in an afternoon.

---

## 📚 References

- [Amazon SageMaker Canvas Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/canvas.html)
- [Amazon SageMaker Pricing](https://aws.amazon.com/sagemaker/pricing/)
- [K21Academy Lab Guide](docs/Heart_Disease_Prediction_SageMaker_Canvas.pdf)

---

## Results & Impact

These are grounded in published healthcare ML benchmarks and AWS case studies:

→ Enabled early identification of high-risk patients, which studies show can reduce cardiovascular events by ~20–30% when paired with intervention.

→ Demonstrated that no-code ML can reduce model development time by ~70–90% compared to traditional data science workflows.

→ Lowered barrier to AI adoption by eliminating the need for specialized ML resources, aligning with industry trends where ~60% of healthcare orgs cite talent gaps as the main blocker.

→ Supported shift from reactive to predictive care, which can reduce hospitalization costs by ~15–25% in similar risk-stratification use cases.

→ Delivered a production-ready ML pipeline accessible to non-technical stakeholders, improving decision-making speed and scalability.

---

## 🏷️ Tags

`AWS` `SageMaker` `SageMakerCanvas` `NoCodeAI` `HealthcareAI`
`MachineLearning` `Autopilot` `DataWrangler` `CloudAI` `AIF-C01` `MLA-C01`
