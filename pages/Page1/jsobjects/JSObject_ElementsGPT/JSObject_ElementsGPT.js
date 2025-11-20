export default {
  /**
   * Validate selected file and return an object { ok: bool, reason?: string }
   */
  validateSelectedFile() {
    const f = FilePicker1.files && FilePicker1.files[0];
    if (!f) return { ok: false, reason: "No file selected" };

    // file size in bytes
    const maxMb = 200;
    const maxBytes = maxMb * 1024 * 1024;
    if (f.size > maxBytes) return { ok: false, reason: `File too large (> ${maxMb} MB)` };

    // optional: restrict types (uncomment if needed)
    // const allowed = ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
    // if (!allowed.includes(f.type)) return { ok:false, reason: "Unsupported file type" };

    return { ok: true };
  },

  /**
   * Handler bound to FilePicker.onFilesSelected
   * We will just validate and optionally preview metadata
   */
  async onFileSelected() {
    const v = this.validateSelectedFile();
    if (!v.ok) {
      // Optionally show a notification
      showAlert(v.reason, "error");
      // Clear the filepicker to force reselect if you want
      // FilePicker1.clear();
      return;
    }

    // Optionally set a short preview on UI widgets
    const f = FilePicker1.files[0];
    // Example: set text widget values (if you have such widgets)
    // FileNameLabel.setText(f.name);
    // FileSizeLabel.setText(Math.round(f.size/1024) + " KB");

    // If you want to auto-run upload on selection, uncomment:
    // await this.uploadCV();
  },

  /**
   * Upload file + user metadata to backend (multipart/form-data)
   * This expects you created UploadCVQuery in Appsmith as described.
   */
  async uploadCV() {
    // Validate
    const v = this.validateSelectedFile();
    if (!v.ok) {
      showAlert(v.reason, "error");
      return { success: false, error: v.reason };
    }

    // Ensure the query exists
    try {
      // Pass additional dynamic data to the query if needed (some Appsmith versions let you pass body)
      // Here we rely on the UploadCVQuery using widget bindings for file and text inputs
      const res = await UploadCVQuery.run();
      if (res && res.responseMeta && res.responseMeta.status === 200) {
        showAlert("Upload successful", "success");
        // Optionally store returned cv_id in a global store or JS object property
        this.latestCvId = res.body && res.body.cv_id ? res.body.cv_id : null;
        return { success: true, data: res.body };
      } else {
        // Res may vary; check response
        console.error("UploadCVQuery result", res);
        showAlert("Upload failed — check console", "error");
        return { success: false, data: res };
      }
    } catch (err) {
      console.error("uploadCV error", err);
      showAlert("Upload error — check console", "error");
      return { success: false, error: err.message || err };
    }
  },

  /**
   * High-level submit invoked by Submit button
   * Orchestrates upload then getRecommendations
   */
  async handleSubmit() {
    // 1. Validate fields (example: require file)
    const v = this.validateSelectedFile();
    if (!v.ok) {
      showAlert(v.reason, "error");
      return;
    }

    // 2. Upload CV
    const up = await this.uploadCV();
    if (!up.success) return;

    // 3. Call recommendations query that expects cv_id or raw text
    // If your backend returns cv_id:
    const cvId = (up.data && up.data.cv_id) ? up.data.cv_id : null;

    try {
      // Example: run a separate query which uses {{ JSObject1.latestCvId }} or pass directly if your query supports params
      const rec = await GetRecommendationQuery.run({ cv_id: cvId: TextInput.text });
      // Display results: set widget values or switch custom widget page
      // Example: set a JSON viewer widget or set properties on your custom widget
      // JSONViewer1.setText(JSON.stringify(rec, null, 2));
      // customWidget1.setPage(2);   // if your widget API supports this
      showAlert("Recommendations ready", "success");
      return rec;
    } catch (err) {
      console.error("recommendation error", err);
      showAlert("Recommendation error", "error");
      return;
    }
  },

  /**
   * Reset the entire UI page (clears filepicker, text inputs, and reset custom widget page)
   */
  resetAll() {
    try {
      FilePicker1.clear();          // clears the selection
    } catch (e) {
      console.warn("clear() may not exist for some versions", e);
      // fallback: set widget value via store if needed
    }
    TextInput1.setText("");
    // Reset any result viewers
    // JSONViewer1.setText("");
    // Reset custom widget to page 1 (this depends on your custom widget API)
    // customWidget1.resetToPage && customWidget1.resetToPage(1);
    showAlert("Page reset", "success");
  }
}
