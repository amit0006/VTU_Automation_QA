/**
 * VTU Automation Frontend Script
 * Handles form submission, status polling, and file download.
 * Uses polling mechanism to check job status periodically instead of waiting for complete response.
 */

// Get DOM elements
const form = document.getElementById("resultForm");
const fileInput = document.getElementById("usnFile");
const urlInput = document.getElementById("urlInput");
const subjectCodesInput = document.getElementById("subjectCodes");
const loading = document.getElementById("loading");
const resultSection = document.getElementById("resultSection");

// Status polling configuration
const POLL_INTERVAL = 2000; // Poll every 2 seconds
const MAX_POLL_ATTEMPTS = 1800; // Maximum 60 minutes (1800 * 2 seconds)
let pollAttempts = 0;
let pollInterval = null;

/**
 * Update loading message with progress information
 */
function updateLoadingMessage(message) {
  if (loading) {
    loading.textContent = message;
  }
}

/**
 * Poll the backend for job status
 * @param {string} jobId - Unique job identifier
 */
async function pollStatus(jobId) {
  try {
    const response = await fetch(`/status/${jobId}`);
    
    if (!response.ok) {
      throw new Error(`Status check failed: ${response.statusText}`);
    }

    const statusData = await response.json();
    
    // Update loading message with progress
    const progressMsg = statusData.progress_percentage 
      ? `Processing... ${statusData.processed_usns}/${statusData.total_usns} USNs (${statusData.progress_percentage}%)`
      : `Processing... ${statusData.current_usn || "Initializing..."}`;
    updateLoadingMessage(progressMsg);

    // Check job status
    if (statusData.status === "completed") {
      // Job completed successfully
      clearInterval(pollInterval);
      pollInterval = null;
      
      if (statusData.file_ready) {
        // Download the file
        await downloadFile(jobId);
      } else {
        throw new Error("Processing completed but file not found.");
      }
    } else if (statusData.status === "failed") {
      // Job failed
      clearInterval(pollInterval);
      pollInterval = null;
      throw new Error(statusData.error || "Processing failed on the server.");
    } else if (statusData.status === "processing" || statusData.status === "pending") {
      // Still processing, continue polling
      pollAttempts++;
      
      // Check if we've exceeded max attempts
      if (pollAttempts >= MAX_POLL_ATTEMPTS) {
        clearInterval(pollInterval);
        pollInterval = null;
        throw new Error("Processing is taking too long. Please check backend logs.");
      }
    }
  } catch (error) {
    // Stop polling on error
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    throw error;
  }
}

/**
 * Download the generated Excel file
 * @param {string} jobId - Unique job identifier
 */
async function downloadFile(jobId) {
  try {
    const response = await fetch(`/download/${jobId}`);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || "Failed to download file.");
    }

    // Get response as Blob (Excel file)
    const blob = await response.blob();
    const fileUrl = window.URL.createObjectURL(blob);

    // Update UI
    loading.classList.add("hidden");
    resultSection.classList.remove("hidden");

    // Setup download button
    document.getElementById("downloadBtn").onclick = () => {
      const a = document.createElement("a");
      a.href = fileUrl;
      a.download = "vtu_structured_results.xlsx";
      a.click();
    };

    // Setup analyze buttons
    document.getElementById("analyzeYes").onclick = () => {
      window.open("https://vtu-dashboard.onrender.com/", "_blank");
    };

    document.getElementById("analyzeNo").onclick = () => {
      window.location.reload();
    };
  } catch (error) {
    console.error("❌ Download error:", error);
    throw error;
  }
}

/**
 * Handle form submission
 */
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const urlValue = urlInput.value.trim();
  const subjectCodesValue = subjectCodesInput.value.trim();

  // Validate inputs
  if (!fileInput.files.length || !urlValue) {
    alert("⚠️ Please upload a CSV and enter the VTU result URL!");
    return;
  }

  // Create form data
  const formData = new FormData();
  formData.append("usn_csv", fileInput.files[0]);
  formData.append("url", urlValue);
  formData.append("subject_codes", subjectCodesValue);

  // Reset polling state
  pollAttempts = 0;
  if (pollInterval) {
    clearInterval(pollInterval);
  }

  // Update UI
  loading.classList.remove("hidden");
  resultSection.classList.add("hidden");
  updateLoadingMessage("Starting processing...");

  try {
    // Submit form and get job ID
    const response = await fetch("/process/", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Failed to start processing. Please check the backend logs.");
    }

    const data = await response.json();
    const jobId = data.job_id;

    if (!jobId) {
      throw new Error("No job ID received from server.");
    }

    // Start polling for status
    updateLoadingMessage("Processing started. Checking status...");
    
    // Poll immediately, then set interval
    await pollStatus(jobId);
    pollInterval = setInterval(() => pollStatus(jobId), POLL_INTERVAL);

  } catch (error) {
    console.error("❌ Error:", error);
    alert("❌ Error: " + error.message);
    loading.classList.add("hidden");
    
    // Clean up polling if it was started
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }
});
