import streamlit as st
from ultralytics import YOLO
from pymongo import MongoClient
from bson.binary import Binary
from bson import ObjectId
import pandas as pd
from datetime import datetime
from PIL import Image
import numpy as np
import io

# ---------------- CONFIG ----------------
MONGO_URL = "mongodb+srv://mlikhith6_db_user:Likhith2912@cluster0.6porzaw.mongodb.net/?appName=Cluster0"
DB_NAME = "pothole-detection"
COLLECTION = "reports"

# ---------------- INIT ----------------
client = MongoClient(MONGO_URL)
db = client[DB_NAME]
collection = db[COLLECTION]

model = YOLO("weights/best.pt")

st.set_page_config(page_title="RoadWise", layout="wide")

# SESSION FIX
if "user_state" not in st.session_state:
    st.session_state.user_state = "idle"


left, right = st.columns(2)

# =====================================================
#                  USER PANEL (LEFT)
# =====================================================
with left:
    st.header("Report a Pothole")

    uploaded = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"], key="upload_user")

    if uploaded:
        img = Image.open(uploaded)
        st.image(img, caption="Uploaded Image", use_container_width=True)

        if img.mode != "RGB":
            img = img.convert("RGB")

        img_np = np.array(img)

        if st.button("Run Detection", key="run_detection"):
            results = model.predict(img_np, conf=0.5, classes=0, verbose=False)
            det = len(results[0].boxes)

            st.session_state.detected = det > 0
            st.session_state.confidence = float(results[0].boxes.conf.max()) if det > 0 else 0.0
            st.session_state.user_state = "detected"

    if st.session_state.user_state == "detected":
        if st.session_state.detected:
            st.error(f"Pothole Detected (Confidence: {st.session_state.confidence:.2f})")
        else:
            st.success("No pothole detected.")

        st.subheader("📍 Enter Details")

        report_name = st.text_input("Report Name (Example: 'Near SRM Gate 3')", key="report_name")
        lat = st.text_input("Latitude", key="lat_user")
        lon = st.text_input("Longitude", key="lon_user")

        if st.button("Submit Report", key="submit_report"):
            if not report_name or not lat or not lon:
                st.error("Please fill all details!")
            else:
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                encoded = Binary(buffer.getvalue())

                data = {
                    "report_name": report_name,
                    "latitude": lat,
                    "longitude": lon,
                    "pothole_found": st.session_state.detected,
                    "confidence": st.session_state.confidence,
                    "status": "Pending",
                    "uploaded_at": datetime.now().isoformat(),
                    "image": encoded
                }

                collection.insert_one(data)
                st.success("Report submitted successfully ✔")
                # ---------------- Show Map Preview ----------------
                if lat and lon:
                    st.write("### 🗺 Location Preview")
                    gmap_url = f"https://www.google.com/maps?q={lat},{lon}&z=18&output=embed"

                st.components.v1.html(
                    f"""
                    <iframe width="100%" height="300"
                    src="{gmap_url}"
                    style="border:0; border-radius: 10px;" allowfullscreen></iframe>
                    """,
                    height=320
                )
                st.session_state.user_state = "done"

    if st.session_state.user_state == "done":
        st.info("Your report has been submitted.")


# =====================================================
#               AUTHORITY PANEL (RIGHT)
# =====================================================
with right:
    st.header("🛑 Authority Access")

    # ---- SIMPLE AUTH ----
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        passkey = st.text_input("Enter Authority Passkey", type="password")
        if st.button("Login"):
            if passkey == "SRM_AUTH_2025":
                st.session_state.auth = True
                st.success("Access Granted ✔")
                st.rerun()
            else:
                st.error("Invalid Passkey")
        st.stop()

    # ---- AUTHORITY PANEL ----
    st.success("Authority Access Granted")

    data = list(collection.find({}))

    if data:
        df = pd.DataFrame([
            {
                "Report Name": d.get("report_name", "Unnamed"),
                "Latitude": d["latitude"],
                "Longitude": d["longitude"],
                "Detected": "Yes" if d["pothole_found"] else "No",
                "Confidence": d["confidence"],
                "Status": d["status"],
                "Uploaded At": d["uploaded_at"],
                "ID": str(d["_id"])   # keep ID hidden but usable
            }
            for d in data
        ])

        # Shown Columns (no ID)
        display_df = df[[
            "Report Name",
            "Latitude",
            "Longitude",
            "Detected",
            "Confidence",
            "Status",
            "Uploaded At"
        ]]

        st.dataframe(display_df, use_container_width=True)

        # -------- Update Status --------
        st.subheader("Update Report Status")
        selected_name = st.selectbox("Select Report", df["Report Name"])

        selected_row = df[df["Report Name"] == selected_name].iloc[0]
        record_id = selected_row["ID"]

        new_status = st.selectbox("New Status", ["Pending", "In Progress", "Completed"])

        if st.button("Save Status Update"):
            collection.update_one(
                {"_id": ObjectId(record_id)},
                {"$set": {"status": new_status}}
            )
            st.success("Status Updated ✔")
            st.rerun()

        # -------- Excel Download --------
        if st.button("Download Excel"):
            display_df.to_excel("pothole_reports.xlsx", index=False)
            st.success("Excel downloaded as pothole_reports.xlsx")

    else:
        st.info("No reports submitted yet.")
