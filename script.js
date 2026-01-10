document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const bulkInput = document.getElementById('bulk-input');
    const singleInput = document.getElementById('single-input');
    const verifyBulkBtn = document.getElementById('verify-bulk-btn');
    const verifySingleBtn = document.getElementById('verify-single-btn');
    const clearBtn = document.getElementById('clear-btn');
    const toast = document.getElementById('toast');
    const statsContainer = document.getElementById('stats-container');
    const statTotal = document.getElementById('stat-total');
    const statValid = document.getElementById('stat-valid');
    const statInvalid = document.getElementById('stat-invalid');
    const statRisky = document.getElementById('stat-risky');
    const statCatchAll = document.getElementById('stat-catchall');
    const resultsArea = document.getElementById('results-area');
    const resultsTableBody = document.querySelector('#results-table tbody');
    const resultCount = document.getElementById('result-count');
    const exportBtn = document.getElementById('export-btn');
    const copyBtn = document.getElementById('copy-btn');
    const exportXlsxBtn = document.getElementById('export-xlsx-btn');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    // Permission Modal Logic
    const permissionModal = document.getElementById('permission-modal');
    const grantBtn = document.getElementById('grant-btn');

    // Show modal on load if not already granted in this session
    if (!sessionStorage.getItem('networkPermissionGranted')) {
        setTimeout(() => {
            permissionModal.classList.add('active');
        }, 500); // Small delay for smooth entrance
    }

    grantBtn.addEventListener('click', () => {
        sessionStorage.setItem('networkPermissionGranted', 'true');
        permissionModal.classList.remove('active');
        // Optional: Show a success toast
        showToast('Network Permissions Granted', 'success');
    });

    // Dark Mode Toggle
    const darkModeToggle = document.getElementById('dark-mode-toggle');

    // Check for saved dark mode preference
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
    }

    darkModeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');

        // Save preference
        if (document.body.classList.contains('dark-mode')) {
            localStorage.setItem('darkMode', 'enabled');
        } else {
            localStorage.setItem('darkMode', 'disabled');
        }
    });

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
        processEmails(emails, true);
    });

    verifySingleBtn.addEventListener('click', () => {
        const email = singleInput.value.trim();
        if (!email) {
            alert('Please enter an email.');
            return;
        }
        processEmails([email], false);
    });

    // Export Buttons
    exportBtn.addEventListener('click', exportToCSV);
    copyBtn.addEventListener('click', copyResults);
    exportXlsxBtn.addEventListener('click', exportToXLSX);

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

    async function processEmails(emailList, isBulk = false) {
        // Reset UI
        resultsTableBody.innerHTML = '';
        currentResults = [];
        resultsArea.classList.remove('hidden');

        const total = emailList.length;
        let processed = 0;
        resultCount.innerText = `0 / ${total}`;

        // Show export buttons
        if (total > 0) {
            exportBtn.style.display = 'inline-flex';
            copyBtn.style.display = 'inline-flex';
            exportXlsxBtn.style.display = 'inline-flex';
        } else {
            exportBtn.style.display = 'none';
            copyBtn.style.display = 'none';
            exportXlsxBtn.style.display = 'none';
        }

        if (isBulk) {
            // Processing in Chunks
            const CHUNK_SIZE = 5;
            statsContainer.style.display = 'flex'; // Show stats immediately (zeros)
            updateStatsUI(calculateStats([])); // Reset stats to 0

            for (let i = 0; i < emailList.length; i += CHUNK_SIZE) {
                const chunk = emailList.slice(i, i + CHUNK_SIZE);

                try {
                    const response = await fetch('/bulk-verify', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ emails: chunk })
                    });

                    if (!response.ok) throw new Error('Bulk verification failed');

                    const data = await response.json();
                    const batchResults = data.results || [];

                    currentResults.push(...batchResults);
                    processed += chunk.length;

                    // Update UI incrementally
                    batchResults.forEach(result => appendRow(result));
                    resultCount.innerText = `${processed} / ${total}`;

                    const stats = calculateStats(currentResults);
                    updateStatsUI(stats);

                } catch (error) {
                    console.error("Bulk error:", error);
                    // Continue with next chunk even if one fails? Or stop? 
                    // Let's add error rows for this chunk so counts match
                    chunk.forEach(email => {
                        const errResult = { email, status: 'error', reason: 'Network/Server Error' };
                        currentResults.push(errResult);
                        appendRow(errResult);
                    });
                    processed += chunk.length;
                    resultCount.innerText = `${processed} / ${total}`;
                }
            }
        } else {
            // Single Processing
            resultCount.innerText = 'Processing...';
            statsContainer.style.display = 'none';
            for (const email of emailList) {
                const result = await verifyEmailBackend(email);
                currentResults.push(result);
                appendRow(result);
            }
            resultCount.innerText = currentResults.length;
        }
    }

    function calculateStats(results) {
        let stats = { total: results.length, valid: 0, invalid: 0, risky: 0, catch_all: 0 };
        results.forEach(r => {
            if (r.status === 'valid') stats.valid++;
            else if (r.status === 'invalid') stats.invalid++;
            else if (r.status === 'catch-all') stats.catch_all++;
            else stats.risky++; // unknown, risky
        });
        return stats;
    }

    function updateStatsUI(stats) {
        statsContainer.style.display = 'flex'; // Turn grid back on
        statTotal.innerText = stats.total;
        statValid.innerText = stats.valid;
        statInvalid.innerText = stats.invalid;
        statRisky.innerText = stats.risky;
        statCatchAll.innerText = stats.catch_all;
    }

    // Call Backend
    async function verifyEmailBackend(email) {
        try {
            const response = await fetch('/verify', {
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

    function copyResults() {
        if (currentResults.length === 0) {
            alert("No results to copy!");
            return;
        }

        // Create tab-separated text for easy pasting into Excel/Sheets
        let text = 'Email\tStatus\tReason\tScore\tProvider\tRisk Level\n';
        currentResults.forEach(r => {
            text += `${r.email}\t${r.status}\t${r.reason}\t${r.score}\t${r.provider}\t${r.risk_level}\n`;
        });

        navigator.clipboard.writeText(text).then(() => {
            showToast('Results copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Copy failed:', err);
            alert('Failed to copy results. Please try again.');
        });
    }

    function exportToXLSX() {
        if (currentResults.length === 0) {
            alert("No results to export!");
            return;
        }

        // Create a simple XLSX-compatible HTML table
        let html = '<table><thead><tr>';
        html += '<th>Email</th><th>Status</th><th>Reason</th><th>Score</th><th>Provider</th><th>Risk Level</th>';
        html += '</tr></thead><tbody>';

        currentResults.forEach(r => {
            html += '<tr>';
            html += `<td>${r.email}</td>`;
            html += `<td>${r.status}</td>`;
            html += `<td>${r.reason}</td>`;
            html += `<td>${r.score}</td>`;
            html += `<td>${r.provider}</td>`;
            html += `<td>${r.risk_level}</td>`;
            html += '</tr>';
        });

        html += '</tbody></table>';

        // Create blob and download
        const blob = new Blob([html], { type: 'application/vnd.ms-excel' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `email-verification-${Date.now()}.xls`;
        a.click();
        URL.revokeObjectURL(url);

        showToast('XLSX Exported Successfully!', 'success');
    }

    function showToast(message = 'Results exported!') {
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
});
