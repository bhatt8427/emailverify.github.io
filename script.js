document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const bulkInput = document.getElementById('bulk-input');
    const singleInput = document.getElementById('single-input');
    const verifyBulkBtn = document.getElementById('verify-bulk-btn');
    const verifySingleBtn = document.getElementById('verify-single-btn');
    const clearBtn = document.getElementById('clear-btn');
    const resultsArea = document.getElementById('results-area');
    const resultsTableBody = document.querySelector('#results-table tbody');
    const resultCount = document.getElementById('result-count');
    const exportBtn = document.getElementById('export-btn');
    const toast = document.getElementById('toast');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    let currentResults = [];

    // --- Event Listeners ---

    // Tab Switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
        });
    });

    // Clear Button
    clearBtn.addEventListener('click', () => {
        bulkInput.value = '';
    });

    // Verify Buttons
    verifyBulkBtn.addEventListener('click', () => {
        const text = bulkInput.value;
        if (!text.trim()) {
            alert('Please enter some emails first.');
            return;
        }
        // Split by newlines, commas, or semicolons
        const emails = text.split(/[\n,;]+/).map(e => e.trim()).filter(e => e);
        processEmails(emails);
    });

    verifySingleBtn.addEventListener('click', () => {
        const email = singleInput.value.trim();
        if (!email) {
            alert('Please enter an email.');
            return;
        }
        processEmails([email]);
    });

    // Export Button
    exportBtn.addEventListener('click', exportToCSV);

    // File Upload Zone
    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    ['dragleave', 'dragend'].forEach(type => {
        dropZone.addEventListener(type, () => {
            dropZone.classList.remove('drag-over');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    function handleFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target.result;
            // Extract emails using a simple regex to handle CSV/TXT consistently
            const emails = content.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g);
            if (emails && emails.length > 0) {
                // Remove duplicates and join with newlines
                bulkInput.value = [...new Set(emails)].join('\n');
                showToast('File loaded successfully!');
            } else {
                alert('No emails found in the file.');
            }
        };
        reader.readAsText(file);
    }


    // --- Core Logic ---

    async function processEmails(emailList) {
        // Reset UI
        resultsTableBody.innerHTML = '';
        currentResults = [];
        resultsArea.classList.remove('hidden');
        resultCount.innerText = 'Processing...';

        // Process each email
        for (const email of emailList) {
            const result = await verifyEmailBackend(email);
            currentResults.push(result);
            appendRow(result);
        }

        resultCount.innerText = currentResults.length;
    }

    // Call Backend
    async function verifyEmailBackend(email) {
        try {
            const response = await fetch('http://localhost:5000/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email: email })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error verifying email:', error);
            return {
                email: email,
                status: 'error',
                reason: 'Backend Error'
            };
        }
    }

    // --- UI Rendering ---

    function appendRow(data) {
        const tr = document.createElement('tr');

        // Status Badge Class
        const badgeClass = data.status; // valid, invalid, unknown, error, risky

        // Checks logic
        const checks = data.checks || {};
        const syntaxClass = checks.syntax ? 'pass' : 'fail';
        const mxClass = checks.mx ? 'pass' : (checks.mx === false ? 'fail' : '');

        let smtpClass = '';
        if (checks.smtp_status === 'valid') smtpClass = 'pass';
        else if (checks.smtp_status === 'invalid') smtpClass = 'fail';
        else smtpClass = 'warn';

        const checksHtml = `
            <div class="checks-container" style="flex-wrap: wrap;">
                <span class="check-pill ${syntaxClass}" title="Syntax Check">SYNTAX</span>
                <span class="check-pill ${mxClass}" title="MX Record Check">MX</span>
                <span class="check-pill ${smtpClass}" title="SMTP Ping">SMTP</span>
                ${checks.catch_all ? '<span class="check-pill warn" title="Catch-All Domain detected">CATCH-ALL</span>' : ''}
            </div>
        `;

        // Confidence Score Color
        const score = data.score || 0;
        let scoreColor = 'var(--error-color)';
        if (score >= 80) scoreColor = 'var(--success-color)';
        else if (score >= 50) scoreColor = 'var(--warning-color)';

        tr.innerHTML = `
            <td>
                <div style="font-weight: 500; word-break: break-all;">${escapeHtml(data.email)}</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">${data.provider || 'Unknown'}</div>
            </td>
            <td>
                ${checksHtml}
            </td>
            <td>
                <div style="font-size: 0.9rem;">${data.reason}</div>
            </td>
            <td>
                <div style="display: flex; flex-direction: column; align-items: start; gap: 5px;">
                     <div style="font-weight: bold; font-size: 1.1rem; color: ${scoreColor}">${score}%</div>
                     <span class="badge ${badgeClass}">${data.status}</span>
                     <div style="font-size: 0.75rem; color: var(--text-muted);">Risk: ${data.risk_level}</div>
                </div>
            </td>
        `;
        resultsTableBody.appendChild(tr);
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // --- CSV Export ---

    function exportToCSV() {
        if (currentResults.length === 0) {
            alert("No results to export!");
            return;
        }

        // Header
        const headers = ["Email", "Provider", "Status", "Score", "Risk Level", "Reason", "Syntax", "MX", "SMTP"];

        // Map data to CSV rows
        const rows = currentResults.map(row => {
            const checks = row.checks || {};
            // Escape quotes in data to prevent CSV breakage
            const escape = (val) => `"${String(val || '').replace(/"/g, '""')}"`;

            return [
                escape(row.email),
                escape(row.provider),
                escape(row.status),
                escape(row.score),
                escape(row.risk_level),
                escape(row.reason),
                escape(checks.syntax ? 'Pass' : 'Fail'),
                escape(checks.mx ? 'Pass' : (checks.mx === false ? 'Fail' : 'N/A')),
                escape(checks.smtp_status || 'N/A')
            ].join(",");
        });

        // Combine header and rows
        const csvContent = [headers.join(","), ...rows].join("\r\n");

        // Use Blob for robust file creation
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);

        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", "verification_results_full.csv");
        link.style.visibility = 'hidden';
        document.body.appendChild(link);

        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        showToast();
    }

    function showToast(message = 'Results exported!') {
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
});
