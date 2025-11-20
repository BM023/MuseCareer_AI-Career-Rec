export default {
	// ----------------------------------------------------
	// STATE MANAGEMENT FUNCTIONS
	// ----------------------------------------------------

	/**
     * Resets the entire application state.
     * This function is executed by the Global Reset Button's (ResetButton) onClick event.
     * @returns {void}
     */
	resetApp: () => {
		// 1. Reset Input Widgets (FilePicker and TextInput)
		resetWidget('FilePicker');
		resetWidget('TextInput');

		// 2. Reset the Custom Widget (RecWidget) to its initial state (e.g., page 1)
		resetWidget('RecWidget');

		// 3. Clear Stored Results
		clearStore('analysis_data');
		clearStore('is_processing');

		// Optional: Show a confirmation message
		showAlert('Application successfully reset.', 'success');
	},

	/**
     * Navigates the Custom Widget (RecWidget) to the next page, cycling through the 4 recs.
     * This function is executed by the Custom Widget's 'Next Page' Button's onClick event.
     * @returns {void}
     */
	goToNextPage: () => {
		const currentPage = RecWidget.pageId;
		const totalPages = 3; // We expect 4 career recommendations
		const nextPage = (currentPage % totalPages) + 1; // Cycles from page 4 back to 1

		RecWidget.setPage(nextPage);
	},

	// ----------------------------------------------------
	// PRIMARY WORKFLOW FUNCTION
	// ----------------------------------------------------

	/**
     * Runs the analysis workflow when the Submit button (SubmitButton) is clicked.
     * @returns {void}
     */
	processSubmission: async () => {
		// 1. Validation Check using the updated widget names
		if (!FilePicker.files.length) {
			showAlert('Please upload your CV file.', 'error');
			return;
		}
		if (!TextInput.text || TextInput.text.trim() === '') {
			showAlert('Please enter your interests and upskilling information.', 'error');
			return;
		}

		// 2. Set Loading State and prepare UI
		storeValue('is_processing', true);
		RecWidget.setPage(1); // Go to page 1 (or a loading page)

		// 3. Run the Gemini API Query (gemini_analysis_query)
		try {
			// gemini_analysis_query.run() automatically sends the data bound in its body.
			const apiResult = await gemini_analysis_query.run();

			// 4. Data Transformation and Storage
			// Store the array of 4 recommendations (which the query is forced to return)
			const recommendations = apiResult.recommendations;
			storeValue('analysis_data', recommendations);

			// 5. Success UI Update
			showAlert('Analysis complete! Check the career recommendations below.', 'success');

		} catch (error) {
			// 6. Error Handling
			console.error("Gemini API Error:", error);
			// Error handling tailored for a capstone project
			showAlert('Analysis failed. Check your Gemini API configuration and network logs.', 'error');

		} finally {
			// 7. Cleanup
			storeValue('is_processing', false);
		}
	}
}