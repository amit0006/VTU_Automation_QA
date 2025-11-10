document.getElementById("resultForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const fileInput = document.getElementById("usnFile");
  const urlInput = document.getElementById("urlInput").value.trim();
  const subjectCodes = document.getElementById("subjectCodes").value.trim();
  const loading = document.getElementById("loading");
  const resultSection = document.getElementById("resultSection");

  // ✅ Validate inputs
  if (!fileInput.files.length || !urlInput) {
    alert("⚠️ Please upload a CSV and enter the VTU result URL!");
    return;
  }

  const formData = new FormData();
  formData.append("usn_csv", fileInput.files[0]);
  formData.append("url", urlInput);
  formData.append("subject_codes", subjectCodes); // Optional

  // UI feedback
  loading.classList.remove("hidden");
  resultSection.classList.add("hidden");

  try {
    // Use relative path so frontend works when served from the same origin as the API
    const response = await fetch("/process/", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Failed to process request. Please check the backend logs.");
    }

    // 📦 Get response as Blob (Excel)
    const blob = await response.blob();
    const fileUrl = window.URL.createObjectURL(blob);

    // 🟢 Update UI
    loading.classList.add("hidden");
    resultSection.classList.remove("hidden");

    // 🧾 Download file
    document.getElementById("downloadBtn").onclick = () => {
      const a = document.createElement("a");
      a.href = fileUrl;
      a.download = "vtu_structured_results.xlsx";
      a.click();
    };

    // Optional analyze buttons
    document.getElementById("analyzeYes").onclick = () => {
      window.open("https://vtu-dashboard.onrender.com/", "_blank");
    };

    document.getElementById("analyzeNo").onclick = () => {
      window.location.reload();
    };
  } catch (error) {
    console.error("❌ Error:", error);
    alert("❌ Error: " + error.message);
  } finally {
    loading.classList.add("hidden");
  }
});
