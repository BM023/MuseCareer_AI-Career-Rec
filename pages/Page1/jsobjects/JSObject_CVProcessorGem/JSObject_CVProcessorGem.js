export default {
    // This function runs when the Submit button is clicked
    process_submission: async () => {
        // 1. Input Validation (Ensure all core inputs exist)
        if (!FilePicker.files.length || !TextInput.text) {
            showAlert('Please upload a CV and enter the additional relevant information.', 'error');
            return; // Stop execution
        }

        // 2. Show Loading State (Optional, but good UX)
        storeValue('is_processing', true);

        // 3. Run the API Query
        try {
            // Note: The Query must be configured to reference the Widget data
            const raw_result = await gemini_analysis.run();

            // 4. Transform and Store Data (Crucial for the Multi-Page Custom Widget)
            // Assuming 'raw_result' is a string/JSON that needs to be parsed and prepared
            const structured_data = transform_llm_output(raw_result);
            storeValue('cv_analysis_data', structured_data);

            // 5. Update UI
            RecWidget.setPage(1); // Go to the first results page
            storeValue('is_processing', false);

        } catch (error) {
            showAlert('AI Analysis Failed: ' + error.message, 'error');
            storeValue('is_processing', false);
        }
    },

    // Example helper function to parse/structure the LLM response for display
    transform_llm_output: (llm_json_string) => {
        // Example: Assume the LLM returns a structured JSON string
        try {
            const parsed = JSON.parse(llm_json_string);
            // This structure should match what your 4 custom widget pages need
            return {
                summary: parsed.key_summary,
                skills_gap: parsed.gaps_identified,
                course_match: parsed.suggested_courses,
                devops_fit: parsed.capstone_project_fit, // Relevant for your project!
            };
        } catch (e) {
            console.error("Failed to parse LLM output:", e);
            return {};
        }
    }
}