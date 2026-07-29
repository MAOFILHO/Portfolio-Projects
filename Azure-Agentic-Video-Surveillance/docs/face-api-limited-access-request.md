# Azure Face API — Limited Access request draft

Use this as the justification text in Microsoft's Face API Limited Access application
(or attach it to an Azure support ticket asking where the current form lives).

---

**Subject:** Limited Access application — Azure AI Face API (facial landmark detection)

**Azure subscription ID:** 960936b9-ecde-465b-be8d-776ca077dcd0
**Resource group:** surveil-rg
**Region:** East US 2

**Intended use case:**
This is a personal/portfolio home-security project ("Azure Real-Time Surveillance") that
analyzes frames from a residential doorbell camera to detect and alert on people at the
front door. We currently use Azure AI Vision Image Analysis 4.0 (Objects/People detection)
for person presence detection. We're requesting Face API access to add facial landmark
detection (eyes, nose, mouth, eyebrows, ears) as a supplementary, on-demand visualization
feature in the dashboard — not for identification, recognition, or verification, and not
processing any data belonging to third parties without their knowledge (the camera covers
a private residence entryway).

**Specific capabilities requested:**
- Face detection with landmarks (`returnFaceLandmarks=true`)
- (If still available at your discretion) the `smile` attribute

**Explicitly NOT requesting:**
- Face identification / verification (1:1 or 1:N matching against an enrolled face list)
- Face recognition, PersonGroup / LargePersonGroup features
- Any biometric identification use case

**Data handling:**
Frames are captured from a residential doorbell camera and a personal webcam, used only by
the account owner, stored in a private Azure Storage account with keyless (managed
identity) RBAC access — no public access, no third-party data sharing.

---

## One thing worth knowing before you apply

Azure actually **removed general emotion classification (happy/sad/angry/surprised/etc.)
from the Face API entirely in 2022** as a Responsible AI change — it's not just gated
behind Limited Access, it no longer exists as a product feature at any access tier. So
even with full approval, you won't be able to get a broad "emotion" reading back from
Azure. The only expression-adjacent signal that may still exist under Limited Access is a
binary `smile` attribute (true/false + confidence) — not a multi-emotion classifier. Worth
keeping expectations calibrated before spending time on the application.
