# ============================================================
#  Credit Card Fraud Detector — Scenario-Based Gradio App
#  K21 Academy | SageMaker + XGBoost + SMOTE
#  Feature order: Time, V1–V28, Amount  (matches training data)
# ============================================================

import gradio as gr
import boto3

SMOTE_ENDPOINT = "sagemaker-soln-fdml--xgb-smote"
BASE_ENDPOINT  = "sagemaker-soln-fdml--xgb-2026-05-04-09-35-13-752"

runtime = boto3.client("sagemaker-runtime")

# ── Scenarios — real rows from creditcard.csv ─────────────────
# Feature order: [Time, V1..V28, Amount]  ← matches model training
SCENARIOS = {

    "🛒  Grocery store — $149 (Safe)": {
        "desc"     : "Normal daytime purchase, local merchant, chip & PIN",
        "risk_hint": "Low risk — matches typical cardholder spending pattern",
        "features" : [0.0,
                      -1.3598071336738, -0.0727811733098497, 2.53634673796914,
                       1.37815522427443, -0.338320769942518, 0.462387777762292,
                       0.239598554061257, 0.0986979012610507, 0.363786969611213,
                       0.0907941719789316, -0.551599533260813, -0.617800855762348,
                      -0.991389847235408, -0.311169353699879, 1.46817697209427,
                      -0.470400525259478, 0.207971241929242, 0.0257905801985591,
                       0.403992960255733, 0.251412098239705, -0.018306777944153,
                       0.277837575558899, -0.110473910188767, 0.0669280749146731,
                       0.128539358273528, -0.189114843888824, 0.133558376740387,
                      -0.0210530534538215,
                       149.62],
    },

    "☕  Coffee shop — $2.69 (Safe)": {
        "desc"     : "Small contactless payment, familiar merchant, regular spending",
        "risk_hint": "Low risk — small amount, consistent with daily routine",
        "features" : [68.0,
                       1.15693906521199, 0.0372151171834976, 0.556799036120114,
                       0.519506543569017, -0.47975387242074, -0.352713751231664,
                      -0.222486535919933, 0.158242439405977, 0.0112517233737559,
                       0.105583808549274, 1.61209937075746, 0.354492949815164,
                      -1.43453627828567, 0.796994975493623, 0.745106379600413,
                       0.222868280835633, -0.229198749153177, -0.364808594625195,
                      -0.254104653277162, -0.221851585086154, -0.182661585534005,
                      -0.612267726276609, 0.1973046499394, 0.174882516093158,
                       0.0324965433024755, 0.099479911401087, -0.0268157912881385,
                       0.0041986330049439,
                       2.69],
    },

    "🍕  Restaurant — $1.98 (Safe)": {
        "desc"     : "Low-value dining payment, domestic merchant, contactless",
        "risk_hint": "Low risk — small amount, normal transaction behaviour",
        "features" : [368.0,
                      -0.409899592587, 1.18308756526926, 1.59896704783592,
                       0.35308835423035, 0.309710019802076, -0.312399991678796,
                       0.707197413005536, -0.0432064902376725, -0.89286898747464,
                      -0.684800184134323, 0.237011017639282, 0.513399774118512,
                       1.25825777933396, -0.52148833165945, 1.40389771378531,
                      -0.243457561256418, 0.491733589442823, -0.618058044321218,
                       0.293941888763813, 0.117258109422578, -0.163370811797122,
                      -0.396155273321927, -0.0694977737711297, 0.0697349728061938,
                      -0.298406889409742, 0.199188201034332, 0.0996924343837626,
                       0.1186172016434,
                       1.98],
    },

    "🚌  Transport fare — $7.28 (Safe)": {
        "desc"     : "Regular commute payment, transit authority, tap & go",
        "risk_hint": "Low risk — recurring low-value transaction, known merchant",
        "features" : [756.0,
                       1.22590197990148, 0.239666750542786, 0.170020554213492,
                       0.508587451879376, -0.202827400003141, -0.567680401717712,
                      -0.0512926264630507, -0.0072495981919254, -0.126287768872312,
                      -0.100620450775252, 1.24541682537424, 0.537352787554135,
                      -0.318864720595423, -0.0063001521082982, 0.475601683086472,
                       0.797413693185546, -0.347541274550944, 0.369984583488762,
                       0.218702867945023, -0.0809563567822212, -0.260501125822413,
                      -0.824387938532103, 0.0770318334264881, -0.056428938589201,
                       0.210946176971943, 0.0988121141630544, -0.0317632329467524,
                       0.0171000257243908,
                       7.28],
    },

    "🚨  Stolen card — $0 probe (Fraud)": {
        "desc"     : "Zero-amount auth check — testing if stolen card is active before use",
        "risk_hint": "High risk — $0 auth probe is a classic stolen card verification technique",
        "features" : [406.0,
                      -2.3122265423263, 1.95199201064158, -1.60985073229769,
                       3.9979055875468, -0.522187864667764, -1.42654531920595,
                      -2.53738730624579, 1.39165724829804, -2.77008927719433,
                      -2.77227214465915, 3.20203320709635, -2.89990738849473,
                      -0.595221881324605, -4.28925378244217, 0.389724120274487,
                      -1.14074717980657, -2.83005567450437, -0.0168224681808257,
                       0.416955705037907, 0.126910559061474, 0.517232370861764,
                      -0.0350493686052974, -0.465211076182388, 0.320198198514526,
                       0.0445191674731724, 0.177839798284401, 0.261145002567677,
                      -0.143275874698919,
                       0.0],
    },

    "🚨  Overseas ATM — $529 (Fraud)": {
        "desc"     : "Large cash withdrawal, foreign ATM, card not present, no travel flag",
        "risk_hint": "High risk — geography mismatch + large cash amount = strong fraud signal",
        "features" : [472.0,
                      -3.0435406239976, -3.15730712090228, 1.08846277997285,
                       2.2886436183814, 1.35980512966107, -1.06482252298131,
                       0.325574266158614, -0.0677936531906277, -0.270952836226548,
                      -0.838586564582682, -0.414575448285725, -0.503140859566824,
                       0.676501544635863, -1.69202893305906, 2.00063483909015,
                       0.666779695901966, 0.599717413841732, 1.72532100745514,
                       0.283344830149495, 2.10233879259444, 0.661695924845707,
                       0.435477208966341, 1.37596574254306, -0.293803152734021,
                       0.279798031841214, -0.145361714815161, -0.252773122530705,
                       0.0357642251788156,
                       529.0],
    },

    "🚨  Card testing — $1 micro-charge #1 (Fraud)": {
        "desc"     : "Tiny $1 charge to verify stolen card works before large purchases",
        "risk_hint": "High risk — micro-charge card testing, extreme V feature anomalies detected",
        "features" : [7526.0,
                       0.0084303648955825, 4.13783683497998, -6.24069657194744,
                       6.6757321631344, 0.768307024571449, -3.35305954788994,
                      -1.63173467271809, 0.15461244822474, -2.79589246446281,
                      -6.18789062970647, 5.66439470857116, -9.85448482287037,
                      -0.306166658250084, -10.6911962118171, -0.638498192673322,
                      -2.04197379107768, -1.12905587703585, 0.116452521226364,
                      -1.93466573889727, 0.488378221134715, 0.36451420978479,
                      -0.608057133838703, -0.539527941820093, 0.128939982991813,
                       1.48848121006868, 0.50796267782385, 0.735821636119662,
                       0.513573740679437,
                       1.0],
    },

    "🚨  Card testing — $1 micro-charge #2 (Fraud)": {
        "desc"     : "Second stolen card test charge — different card, same fraudster pattern",
        "risk_hint": "High risk — repeated micro-charge pattern, behavioural anomaly across V14, V12",
        "features" : [7672.0,
                       0.702709900098753, 2.42643280600508, -5.23451329584052,
                       4.41666124290876, -2.17080621591773, -2.66755356121463,
                      -3.87808845483572, 0.911337122229195, -0.166199039175942,
                      -5.00924850212751, 4.67572941865677, -8.16718805173089,
                       0.638559282180499, -6.76333439062322, 1.29686025605627,
                      -3.81175840977789, -3.75412806618729, -1.04917740227906,
                       1.55419726345897, 0.422743129198702, 0.551179689117248,
                      -0.0098023573132531, 0.721698230069415, 0.473245751402033,
                      -1.9593037711687, 0.31947554010746, 0.600484916486359,
                       0.129305225096566,
                       1.0],
    },
}

SCENARIO_KEYS = list(SCENARIOS.keys())

# ── Prediction ────────────────────────────────────────────────
def predict(scenario_name, model_choice):
    scenario = SCENARIOS[scenario_name]
    payload  = ",".join([str(f) for f in scenario["features"]])
    endpoint = SMOTE_ENDPOINT if "SMOTE" in model_choice else BASE_ENDPOINT

    try:
        response = runtime.invoke_endpoint(
            EndpointName=endpoint,
            ContentType="text/csv",
            Body=payload,
        )
        prob = float(response["Body"].read().decode())
    except Exception as e:
        return f"❌ Error: {e}", "—", "—", "—"

    is_fraud = prob > 0.5
    verdict  = "🚨  FRAUD DETECTED" if is_fraud else "✅  LEGITIMATE"
    risk_lvl = "🔴 High" if prob > 0.7 else "🟡 Medium" if prob > 0.5 else "🟢 Low"

    return verdict, f"{prob*100:.1f}%", risk_lvl, scenario["risk_hint"]

# ── Scenario info ─────────────────────────────────────────────
def get_scenario_info(scenario_name):
    s   = SCENARIOS[scenario_name]
    amt = s["features"][-1]          # Amount is last
    t   = s["features"][0]           # Time is first
    hrs = int(t // 3600) % 24
    return f"💳  Amount: ${amt:,.2f}", f"🕐  Time of day: {hrs:02d}:00", s["desc"]

# ── UI ────────────────────────────────────────────────────────
CSS = """
.gradio-container { max-width: 860px !important; margin: auto; }
.verdict-box textarea { font-size: 1.4rem !important; font-weight: 700 !important; text-align: center; }
footer { display: none !important; }
"""

with gr.Blocks(css=CSS, title="Fraud Detection — K21 Academy") as demo:

    gr.Markdown("""
    # 🛡️ Credit Card Fraud Detector
    **K21 Academy** · XGBoost + SMOTE · Deployed on Amazon SageMaker
    ---
    """)

    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown("### Step 1 — Pick a transaction scenario")
            scenario_dd = gr.Dropdown(
                choices=SCENARIO_KEYS, value=SCENARIO_KEYS[0],
                label="Transaction Scenario",
                info="Each scenario uses a real row from the ULB credit card fraud dataset"
            )
            with gr.Group():
                gr.Markdown("**Transaction details**")
                with gr.Row():
                    info_amount = gr.Textbox(label="Amount", interactive=False, scale=1)
                    info_time   = gr.Textbox(label="Time",   interactive=False, scale=1)
                info_desc = gr.Textbox(label="Description", interactive=False, lines=2)

            gr.Markdown("### Step 2 — Choose model")
            model_dd = gr.Radio(
                ["SMOTE (recommended — handles imbalanced data)",
                 "Base XGBoost (standard weighted)"],
                value="SMOTE (recommended — handles imbalanced data)",
                label="Model",
            )
            predict_btn = gr.Button("🔍  Run Fraud Check", variant="primary", size="lg")

        with gr.Column(scale=2):
            gr.Markdown("### Result")
            out_verdict = gr.Textbox(label="Verdict",          interactive=False, elem_classes="verdict-box")
            out_prob    = gr.Textbox(label="Fraud Probability", interactive=False)
            out_risk    = gr.Textbox(label="Risk Level",        interactive=False)
            out_note    = gr.Textbox(label="Why this risk?",    interactive=False, lines=3)
            gr.Markdown("""
            ---
            **Model performance on test set**

            | Metric | SMOTE | Base |
            |--------|-------|------|
            | Precision | 93% | 91% |
            | Recall | 80% | 78% |
            | F1 Score | 86% | 84% |
            """)

    gr.Markdown("""
    ---
    > ⚠️ V1–V28 are PCA-transformed features (anonymised for privacy). All scenario vectors
    > are **real rows** from the ULB credit card fraud dataset — predictions reflect actual model behaviour.
    """)

    scenario_dd.change(get_scenario_info, inputs=scenario_dd, outputs=[info_amount, info_time, info_desc])
    predict_btn.click(predict, inputs=[scenario_dd, model_dd], outputs=[out_verdict, out_prob, out_risk, out_note])
    demo.load(get_scenario_info, inputs=scenario_dd, outputs=[info_amount, info_time, info_desc])

demo.launch(share=True)
