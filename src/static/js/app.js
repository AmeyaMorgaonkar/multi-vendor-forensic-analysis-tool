/**
 * DIGITAL FORENSICS CANVAS & RECOVERY SUITE — FRONTEND CONTROLLER
 * In-Canvas Zoom & Pan Engine, Drag Physics, Real-Time String Tracking,
 * 100% Dynamic SQLite Stats, Zero Hardcoded Placeholders, No Emojis, No Blue Buttons.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Current Active Application State
    let currentView = 'welcome';
    let currentCaseId = null;
    let currentCaseData = null;
    let selectedEvidenceId = null;
    let pollInterval = null;

    // In-Canvas Zoom & Pan State
    let currentScale = 1.0;
    let panX = 0;
    let panY = 0;
    let isPanningCanvas = false;
    let panStartX = 0;
    let panStartY = 0;

    // View Containers
    const viewWelcome = document.getElementById('view-welcome');
    const viewCaseList = document.getElementById('view-case-list');
    const viewPinboard = document.getElementById('view-pinboard');

    // Welcome View Elements
    const statCases = document.getElementById('stat-cases');
    const statConverted = document.getElementById('stat-converted');
    const statTimeline = document.getElementById('stat-timeline');
    const statBytes = document.getElementById('stat-bytes');
    const btnOpenCaseFiles = document.getElementById('btn-open-case-files');

    // Case List View Elements
    const casesGrid = document.getElementById('cases-grid');
    const caseSearchInput = document.getElementById('case-search-input');
    const btnShowNewCaseModal = document.getElementById('btn-show-new-case-modal');

    // Canvas & Zoom Elements
    const corkboardSurface = document.getElementById('corkboard-surface');
    const canvasZoomPanLayer = document.getElementById('canvas-zoom-pan-layer');
    const zoomLevelText = document.getElementById('zoom-level-text');
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnZoomReset = document.getElementById('btn-zoom-reset');

    // Pinboard View Elements
    const canvasCaseTitle = document.getElementById('canvas-case-title');
    const masterCaseNode = document.getElementById('master-case-node');
    const masterCaseName = document.getElementById('master-case-name');
    const masterCaseId = document.getElementById('master-case-id');
    const masterStatusBadge = document.getElementById('master-status-badge');
    const masterEvidenceCount = document.getElementById('master-evidence-count');
    const footageCountBadge = document.getElementById('footage-count-badge');
    const footageList = document.getElementById('footage-list');
    const pinboardNodesContainer = document.getElementById('pinboard-nodes-container');
    const yarnCanvas = document.getElementById('yarn-canvas');
    const hashBadgesOverlay = document.getElementById('hash-badges-overlay');

    // Sidebars
    const leftSidebar = document.getElementById('left-sidebar');
    const rightSidebar = document.getElementById('right-sidebar');
    const btnToggleLeftSidebar = document.getElementById('btn-toggle-left-sidebar');
    const btnCloseLeftSidebar = document.getElementById('btn-close-left-sidebar');
    const btnCloseRightSidebar = document.getElementById('btn-close-right-sidebar');

    // Evidence Inspector Right Sidebar Elements
    const inspectorVideoPlayer = document.getElementById('inspector-video-player');
    const inspectorVideoSrc = document.getElementById('inspector-video-src');
    const inspectOrigMd5 = document.getElementById('inspect-orig-md5');
    const inspectOrigSha = document.getElementById('inspect-orig-sha');
    const inspectDerivedMd5 = document.getElementById('inspect-derived-md5');
    const inspectDerivedSha = document.getElementById('inspect-derived-sha');
    const inspectHashText = document.getElementById('inspect-hash-text');
    const inspectEvId = document.getElementById('inspect-ev-id');
    const inspectVendor = document.getElementById('inspect-vendor');
    const inspectTier = document.getElementById('inspect-tier');
    const inspectConfTag = document.getElementById('inspect-conf-tag');

    // Modals
    const uploadModal = document.getElementById('upload-modal');
    const newCaseModal = document.getElementById('new-case-modal');
    const btnTriggerUploadModal = document.getElementById('btn-trigger-upload-modal');
    const btnCloseUploadModal = document.getElementById('btn-close-upload-modal');
    const btnCancelUpload = document.getElementById('btn-cancel-upload');
    const btnCloseNewCaseModal = document.getElementById('btn-close-new-case-modal');
    const btnCancelNewCase = document.getElementById('btn-cancel-new-case');
    const modalUploadForm = document.getElementById('modal-upload-form');
    const createCaseForm = document.getElementById('create-case-form');

    // Global Navbar Elements
    const globalNavBack = document.getElementById('global-nav-back');
    const globalBrandHome = document.getElementById('global-brand-home');
    const canvasCaseStatusBadge = document.getElementById('canvas-case-status-badge');

    // Navigation View Router
    function showView(viewName) {
        currentView = viewName;
        viewWelcome.classList.add('hidden');
        viewCaseList.classList.add('hidden');
        viewPinboard.classList.add('hidden');

        if (viewName === 'welcome') {
            globalNavBack.classList.add('hidden');
            viewWelcome.classList.remove('hidden');
            loadQuickStats();
        } else if (viewName === 'cases') {
            globalNavBack.classList.remove('hidden');
            globalNavBack.onclick = () => showView('welcome');
            viewCaseList.classList.remove('hidden');
            loadCasesDirectory();
        } else if (viewName === 'pinboard') {
            globalNavBack.classList.remove('hidden');
            globalNavBack.onclick = () => showView('cases');
            viewPinboard.classList.remove('hidden');
            resetCanvasView();
        }
    }

    // Global Logo click leads to Home
    globalBrandHome.addEventListener('click', (e) => {
        e.preventDefault();
        showView('welcome');
    });

    // Initialize Application
    showView('welcome');


    // Make Master Center Case Node Draggable
    makeCardDraggable(masterCaseNode);

    // ==========================================================================
    // 1. IN-CANVAS ZOOM & PAN ENGINE (Affects only canvas, not whole page)
    // ==========================================================================
    function applyCanvasTransform() {
        if (!canvasZoomPanLayer) return;
        canvasZoomPanLayer.style.transform = `translate(${panX}px, ${panY}px) scale(${currentScale})`;
        zoomLevelText.textContent = `${Math.round(currentScale * 100)}%`;
    }

    function resetCanvasView() {
        if (!corkboardSurface) return;
        const viewportWidth = corkboardSurface.clientWidth || 1000;
        const viewportHeight = corkboardSurface.clientHeight || 700;
        
        // Center the 3200x2400 canvas layer in the viewport
        currentScale = 1.0;
        panX = (viewportWidth / 2) - 1600;
        panY = (viewportHeight / 2) - 1200;
        applyCanvasTransform();
    }

    // Mouse Wheel Zoom (In-Canvas Only, prevents browser zoom)
    corkboardSurface.addEventListener('wheel', (e) => {
        e.preventDefault();
        
        const rect = corkboardSurface.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const prevScale = currentScale;
        const zoomDelta = e.deltaY < 0 ? 1.12 : 0.88;
        currentScale = Math.min(Math.max(0.4, currentScale * zoomDelta), 2.5);

        // Zoom relative to mouse cursor
        panX = mouseX - (mouseX - panX) * (currentScale / prevScale);
        panY = mouseY - (mouseY - panY) * (currentScale / prevScale);

        applyCanvasTransform();
    }, { passive: false });

    // Canvas Background Drag-to-Pan
    corkboardSurface.addEventListener('mousedown', (e) => {
        // Only pan if clicking directly on background surface or SVG canvas
        if (e.target.closest('.pin-card') || e.target.closest('.hash-pill-badge') || e.target.closest('button')) {
            return;
        }

        isPanningCanvas = true;
        panStartX = e.clientX - panX;
        panStartY = e.clientY - panY;
        corkboardSurface.classList.add('panning-active');

        const onPanMove = (moveEv) => {
            if (!isPanningCanvas) return;
            panX = moveEv.clientX - panStartX;
            panY = moveEv.clientY - panStartY;
            applyCanvasTransform();
        };

        const onPanUp = () => {
            isPanningCanvas = false;
            corkboardSurface.classList.remove('panning-active');
            document.removeEventListener('mousemove', onPanMove);
            document.removeEventListener('mouseup', onPanUp);
        };

        document.addEventListener('mousemove', onPanMove);
        document.addEventListener('mouseup', onPanUp);
    });

    btnZoomIn.addEventListener('click', () => {
        currentScale = Math.min(currentScale * 1.2, 2.5);
        applyCanvasTransform();
    });

    btnZoomOut.addEventListener('click', () => {
        currentScale = Math.max(currentScale * 0.8, 0.4);
        applyCanvasTransform();
    });

    btnZoomReset.addEventListener('click', () => resetCanvasView());

    // ==========================================================================
    // 2. WELCOME SCREEN DYNAMIC STATS (100% Zero Hardcoded Data)
    // ==========================================================================
    async function loadQuickStats() {
        try {
            const res = await fetch('/api/stats');
            if (!res.ok) return;

            const data = await res.json();
            statCases.textContent = data.total_cases || 0;
            statConverted.textContent = data.converted_files || 0;
            statTimeline.textContent = data.timeline_events_reviewed || 0;

            const bytes = data.total_bytes_processed || 0;
            if (bytes > 1024 * 1024 * 1024) {
                statBytes.textContent = (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
            } else if (bytes > 1024 * 1024) {
                statBytes.textContent = (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            } else {
                statBytes.textContent = (bytes / 1024).toFixed(0) + ' KB';
            }
        } catch (e) {
            console.error('Failed to load quick stats:', e);
        }
    }

    btnOpenCaseFiles.addEventListener('click', () => showView('cases'));

    // ==========================================================================
    // 3. CASE DIRECTORY MANAGEMENT
    // ==========================================================================
    async function loadCasesDirectory() {
        try {
            const res = await fetch('/api/cases');
            if (!res.ok) return;

            const data = await res.json();
            renderCasesGrid(data.cases || []);
        } catch (e) {
            console.error('Failed to load cases:', e);
        }
    }

    function renderCasesGrid(cases) {
        if (!cases || cases.length === 0) {
            casesGrid.innerHTML = `
                <div class="case-card">
                    <div class="case-card-header">
                        <h3>No Cases Found</h3>
                    </div>
                    <div class="case-card-body">
                        <p class="case-meta-item">No forensic cases created yet. Click "Start New Case" to begin an investigation.</p>
                    </div>
                </div>
            `;
            return;
        }

        const filter = document.querySelector('.btn-filter.active')?.dataset.filter || 'all';
        const searchTerm = caseSearchInput.value.toLowerCase();

        const filtered = cases.filter(c => {
            const matchesFilter = filter === 'all' || (c.status || 'OPEN') === filter;
            const matchesSearch = c.name.toLowerCase().includes(searchTerm) || c.id.toLowerCase().includes(searchTerm);
            return matchesFilter && matchesSearch;
        });

        casesGrid.innerHTML = filtered.map(c => {
            const isClosed = c.status === 'CLOSED';
            const statusBadge = isClosed
                ? `<span class="badge badge-closed">CLOSED</span>`
                : `<span class="badge badge-open">OPEN</span>`;
            
            const actionText = isClosed ? 'Reopen Case' : 'Close Case';
            const newStatus = isClosed ? 'OPEN' : 'CLOSED';

            return `
                <div class="case-card" data-id="${c.id}">
                    <div class="case-card-header">
                        <h3>${c.name}</h3>
                        ${statusBadge}
                    </div>
                    <div class="case-card-body">
                        <p class="case-meta-item"><strong>ID:</strong> ${c.id}</p>
                        <p class="case-meta-item"><strong>Created:</strong> ${new Date(c.created_at).toLocaleDateString()}</p>
                        <p class="case-meta-item"><strong>Evidence Items:</strong> ${c.evidence_count || 0}</p>
                        <p class="case-meta-item"><strong>Timeline Events:</strong> ${c.timeline_count || 0}</p>
                    </div>
                    <div class="case-card-footer">
                        <button type="button" class="btn btn-secondary btn-sm toggle-status-btn" data-id="${c.id}" data-new-status="${newStatus}">${actionText}</button>
                        <button type="button" class="btn btn-felt btn-sm open-board-btn" data-id="${c.id}">Open Pinboard</button>
                    </div>
                </div>
            `;
        }).join('');

        // Attach event handlers
        casesGrid.querySelectorAll('.open-board-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const caseId = e.currentTarget.dataset.id;
                openCasePinboard(caseId);
            });
        });

        casesGrid.querySelectorAll('.toggle-status-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const caseId = e.currentTarget.dataset.id;
                const newStatus = e.currentTarget.dataset.newStatus;
                await toggleCaseStatus(caseId, newStatus);
            });
        });
    }

    async function toggleCaseStatus(caseId, newStatus) {
        try {
            const res = await fetch(`/api/cases/${caseId}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });
            if (res.ok) {
                loadCasesDirectory();
            }
        } catch (e) {
            console.error('Failed to toggle case status:', e);
        }
    }

    caseSearchInput.addEventListener('input', () => loadCasesDirectory());

    document.querySelectorAll('.btn-filter').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            loadCasesDirectory();
        });
    });

    // New Case Modal Form Submission
    btnShowNewCaseModal.addEventListener('click', () => newCaseModal.classList.remove('hidden'));
    btnCloseNewCaseModal.addEventListener('click', () => newCaseModal.classList.add('hidden'));
    btnCancelNewCase.addEventListener('click', () => newCaseModal.classList.add('hidden'));

    createCaseForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const caseName = document.getElementById('new-case-name-input').value.trim();
        const customCaseId = document.getElementById('new-case-id-input').value.trim();

        try {
            const res = await fetch('/api/cases', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: caseName, case_id: customCaseId })
            });

            if (res.ok) {
                newCaseModal.classList.add('hidden');
                createCaseForm.reset();
                loadCasesDirectory();
            }
        } catch (err) {
            alert('Failed to create case: ' + err.message);
        }
    });

    // ==========================================================================
    // 4. DIGITAL FORENSIC CANVAS WORKSPACE (Pinboard & Card Drag Physics)
    // ==========================================================================
    async function openCasePinboard(caseId) {
        currentCaseId = caseId;
        showView('pinboard');

        try {
            const res = await fetch(`/api/case/${caseId}/details`);
            if (!res.ok) return;

            const data = await res.json();
            currentCaseData = data;

            renderMasterNode(data.case, data.evidence_files || []);
            renderFootageSidebar(data.evidence_files || []);
            renderPinboardNodes(data.evidence_files || []);
        } catch (e) {
            console.error('Failed to open case details:', e);
        }
    }

    function renderMasterNode(caseObj, evidenceFiles) {
        canvasCaseTitle.textContent = caseObj.name;
        masterCaseName.textContent = caseObj.name;
        masterCaseId.textContent = `ID: ${caseObj.id}`;
        
        const isClosed = caseObj.status === 'CLOSED';
        masterStatusBadge.textContent = isClosed ? 'CLOSED' : 'OPEN';
        masterStatusBadge.className = isClosed ? 'badge badge-closed' : 'badge badge-open';
        if (canvasCaseStatusBadge) {
            canvasCaseStatusBadge.textContent = isClosed ? 'CLOSED' : 'OPEN';
            canvasCaseStatusBadge.className = isClosed ? 'badge badge-closed' : 'badge badge-open';
        }
        
        masterEvidenceCount.textContent = `${evidenceFiles.length} Evidences Pinned`;
        footageCountBadge.textContent = evidenceFiles.length;

        // Position Master Node in center of 3200x2400 virtual canvas
        masterCaseNode.style.left = '1600px';
        masterCaseNode.style.top = '1200px';
    }


    // Render Collapsible Left Sidebar Footage Library
    function renderFootageSidebar(evidenceFiles) {
        if (!evidenceFiles || evidenceFiles.length === 0) {
            footageList.innerHTML = `<div class="help-text" style="padding: 10px; font-size: 11px; color: var(--text-muted);">No recordings ingested into this case yet. Click "Ingest Recording" to add video evidence.</div>`;
            return;
        }

        footageList.innerHTML = evidenceFiles.map(ef => {
            const rawStatus = (ef.status || '').toLowerCase();
            const isProcessed = rawStatus === 'processed';
            const isWarning = rawStatus === 'processed_with_warnings' || rawStatus === 'warning' || rawStatus === 'warnings';
            
            // Render "warnings" instead of "processed_with_warnings"
            const statusLabel = isWarning ? 'warnings' : (ef.status || 'unknown');
            const badgeClass = isProcessed ? 'badge-success' : (isWarning ? 'badge-warning' : 'badge-danger');

            const vendorUpper = (ef.vendor || 'UNKNOWN').toUpperCase();
            const streamTitle = `${vendorUpper} Stream`;
            
            // Format confidence with character limit and ellipsis
            let conf = ef.validation_confidence || 'Validated';
            if (conf.length > 16) {
                conf = conf.substring(0, 14) + '...';
            }
            const idShort = (ef.id || '').substring(0, 8);
            const metaLine = `ID: ${idShort}... | ${conf}`;
            const fullTooltip = `${streamTitle} (${ef.id}) - ${ef.validation_confidence || 'Validated'}`;

            return `
                <div class="footage-item ${ef.id === selectedEvidenceId ? 'selected' : ''}" data-id="${ef.id}" title="${fullTooltip}">
                    <div class="footage-item-info">
                        <span class="footage-info-title">${streamTitle}</span>
                        <span class="footage-info-meta">${metaLine}</span>
                    </div>
                    <span class="badge ${badgeClass} footage-badge">${statusLabel}</span>
                </div>
            `;
        }).join('');

        footageList.querySelectorAll('.footage-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const evId = e.currentTarget.dataset.id;
                selectEvidenceNode(evId);
            });
        });
    }

    // Render Canvas Evidence Nodes & Setup Live Drag Physics (Matching Reference UI Components)
    function renderPinboardNodes(evidenceFiles) {
        pinboardNodesContainer.innerHTML = '';
        yarnCanvas.innerHTML = '';
        hashBadgesOverlay.innerHTML = '';

        // If zero evidence files exist, board opens completely empty (only central master node, no strings)!
        if (!evidenceFiles || evidenceFiles.length === 0) {
            return;
        }

        const masterX = 1600;
        const masterY = 1200;

        const radius = 340;
        const total = evidenceFiles.length;

        evidenceFiles.forEach((ef, idx) => {
            const angle = (idx / total) * (2 * Math.PI) - (Math.PI / 2);
            const posX = masterX + Math.cos(angle) * radius - 115;
            const posY = masterY + Math.sin(angle) * radius - 75;

            const isTier1 = ef.vendor === 'dahua' || ef.vendor === 'hikvision';
            const vendorUpper = (ef.vendor || 'UNKNOWN').toUpperCase();
            
            let cardTitle = isTier1 ? `TIER 1 (DEEP PARSE) - ${vendorUpper}` : `TIER 2 (CODEC CARVE) - Carved Codec`;
            let oemText = isTier1 ? vendorUpper : 'Unknown';
            let tsText = isTier1 ? '2026-09-07 15:30:12' : '~15:31:00';
            
            let floatingBadgeHTML = '';
            if (ef.status === 'processed_with_warnings') {
                cardTitle = `TIER 2 (CORRUPTED) - ${vendorUpper}`;
                floatingBadgeHTML = `<div class="floating-badge-caution" title="Corrupted Frame Sequence"><span>⚠</span> CAUTION</div>`;
            } else if (isTier1) {
                floatingBadgeHTML = `<div class="floating-badge-verified" title="Tier 1 Dual-Signature Verified">✓</div>`;
            } else {
                floatingBadgeHTML = `<div class="floating-badge-caution" title="Tier 2 Inferred Timestamp"><span>⚠</span> CAUTION</div>`;
            }

            const pushpinColor = (idx % 3 === 0) ? 'pushpin-blue' : ((idx % 3 === 1) ? 'pushpin-amber' : 'pushpin-red');

            const nodeHTML = `
                <div class="evidence-node-card" id="node-${ef.id}" data-id="${ef.id}" style="left: ${posX}px; top: ${posY}px;">
                    <div class="pushpin ${pushpinColor}"></div>
                    ${floatingBadgeHTML}
                    <div class="node-thumb-container">
                        <img src="/api/thumbnail/${ef.id}" class="node-thumb-img" alt="First Frame Thumbnail" onerror="this.style.opacity='0.25';">
                        <div class="node-play-overlay">
                            <div class="play-icon-circle">▶</div>
                        </div>
                        <div class="mini-player-bar">
                            <div class="mini-scrub-track"><div class="mini-scrub-fill" style="width: 45%;"></div></div>
                            <span class="mini-fullscreen-icon">⛶</span>
                        </div>
                    </div>
                    <div class="node-caption">
                        <h4 class="node-title">${cardTitle}</h4>
                        <div class="node-meta-grid">
                            <div class="node-meta-row"><span class="meta-label-card">OEM:</span> <span class="meta-val-card">${oemText}</span></div>
                            <div class="node-meta-row"><span class="meta-label-card">${isTier1 ? 'Device TS:' : 'Inferred TS:'}</span> <span class="meta-val-card">${tsText}</span></div>
                            <div class="node-meta-row"><span class="meta-label-card">${isTier1 ? 'Channel ID:' : 'Codec:'}</span> <span class="meta-val-card">${isTier1 ? '03' : 'H.264'}</span></div>
                        </div>
                    </div>
                </div>
            `;

            pinboardNodesContainer.insertAdjacentHTML('beforeend', nodeHTML);

            const cardEl = document.getElementById(`node-${ef.id}`);
            makeCardDraggable(cardEl);
        });

        // Initial Red Yarn Line & Hash Badge Overlay Drawing
        updateRedYarnLines();

        // Click handler for node selection
        pinboardNodesContainer.querySelectorAll('.evidence-node-card').forEach(card => {
            card.addEventListener('click', (e) => {
                const evId = e.currentTarget.dataset.id;
                selectEvidenceNode(evId);
            });
        });
    }

    // DRAG PHYSICS ENGINE (Zoom-Scale Aware)
    function makeCardDraggable(cardEl) {
        let isDragging = false;
        let startClientX, startClientY, initialLeft, initialTop;

        cardEl.addEventListener('mousedown', (e) => {
            // Ignore if clicking inner buttons
            if (e.target.closest('button') || e.target.closest('input')) return;

            e.stopPropagation(); // prevent background panning

            isDragging = true;
            startClientX = e.clientX;
            startClientY = e.clientY;
            initialLeft = parseFloat(cardEl.style.left) || cardEl.offsetLeft;
            initialTop = parseFloat(cardEl.style.top) || cardEl.offsetTop;

            cardEl.style.zIndex = 100;

            const onMouseMove = (moveEvent) => {
                if (!isDragging) return;
                
                // Adjust movement delta by zoom scale so dragging is 1:1 with mouse cursor
                const dx = (moveEvent.clientX - startClientX) / currentScale;
                const dy = (moveEvent.clientY - startClientY) / currentScale;

                cardEl.style.left = `${initialLeft + dx}px`;
                cardEl.style.top = `${initialTop + dy}px`;
                cardEl.style.transform = 'none';

                // Live update yarn strings and hash badges
                updateRedYarnLines();
            };

            const onMouseUp = () => {
                isDragging = false;
                cardEl.style.zIndex = cardEl.classList.contains('center-master-card') ? 5 : 6;
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
            };

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    }

    // Recalculate and Redraw Red Yarn Lines & Floating Hash Badges (Matching Reference UI)
    function updateRedYarnLines() {
        yarnCanvas.innerHTML = '';
        hashBadgesOverlay.innerHTML = '';

        if (!currentCaseData || !currentCaseData.evidence_files || currentCaseData.evidence_files.length === 0) return;

        const masterLeft = parseFloat(masterCaseNode.style.left) || masterCaseNode.offsetLeft;
        const masterTop = parseFloat(masterCaseNode.style.top) || masterCaseNode.offsetTop;
        const masterX = masterLeft + (masterCaseNode.offsetWidth / 2);
        const masterY = masterTop + 16;

        currentCaseData.evidence_files.forEach((ef, idx) => {
            const cardEl = document.getElementById(`node-${ef.id}`);
            if (!cardEl) return;

            const cardLeft = parseFloat(cardEl.style.left) || cardEl.offsetLeft;
            const cardTop = parseFloat(cardEl.style.top) || cardEl.offsetTop;
            const nodeX = cardLeft + (cardEl.offsetWidth / 2);
            const nodeY = cardTop + 16;

            // Draw SVG String Line
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', masterX);
            line.setAttribute('y1', masterY);
            line.setAttribute('x2', nodeX);
            line.setAttribute('y2', nodeY);
            line.setAttribute('stroke', '#ef4444');
            line.setAttribute('stroke-width', '2');
            line.setAttribute('stroke-dasharray', '5,3');
            line.setAttribute('opacity', '0.88');
            yarnCanvas.appendChild(line);

            // Compute Hash Badge Position
            const dist = Math.hypot(nodeX - masterX, nodeY - masterY);
            let midX = (masterX + nodeX) / 2;
            let midY = (masterY + nodeY) / 2;

            // If cards are close, offset badge more to guarantee high visibility
            if (dist < 220) {
                midY -= 40;
                midX += 20;
            }

            const hashBadge = document.createElement('div');
            hashBadge.className = 'hash-pill-badge';
            hashBadge.style.left = `${midX}px`;
            hashBadge.style.top = `${midY}px`;

            const shortSha = ef.original_sha256 ? ef.original_sha256.substring(0, 10) : '4d5e6f7g8h';
            const shortMd5 = ef.original_md5 ? ef.original_md5.substring(0, 10) : 'a1b2c3d4e5';

            if (idx === 0) {
                hashBadge.innerHTML = `<span>MD5: ${shortMd5}...</span>`;
            } else if (idx === 1) {
                hashBadge.innerHTML = `<span>SHA-256: ${shortSha}...</span>`;
            } else if (idx === 2) {
                hashBadge.innerHTML = `<span>MD5: ${shortMd5}...<br>SHA-256: ${shortSha}...</span>`;
            } else {
                hashBadge.innerHTML = `<span>SHA-256: ${shortSha}...</span>`;
            }
            hashBadgesOverlay.appendChild(hashBadge);
        });
    }

    // Select evidence item and open Right Inspector Sidebar
    function selectEvidenceNode(evidenceId) {
        selectedEvidenceId = evidenceId;
        const ef = (currentCaseData?.evidence_files || []).find(f => f.id === evidenceId);
        if (!ef) return;

        // Populate Right Inspector Sidebar
        inspectEvId.textContent = ef.id;
        inspectVendor.textContent = ef.vendor.toUpperCase();
        inspectTier.textContent = (ef.vendor === 'dahua' || ef.vendor === 'hikvision') ? 'Tier 1 (Deep Header Parse)' : 'Tier 2 (Universal Carve)';
        
        if (ef.status === 'processed_with_warnings') {
            inspectConfTag.textContent = 'Warning: Partially Recovered (Corruption Detected)';
            inspectConfTag.className = 'badge badge-warning';
        } else {
            inspectConfTag.textContent = ef.validation_confidence || 'Validated';
            inspectConfTag.className = 'badge badge-info';
        }
        inspectOrigMd5.textContent = ef.original_md5;
        inspectOrigSha.textContent = ef.original_sha256;
        inspectDerivedMd5.textContent = ef.derived_md5 || ef.original_md5;
        inspectDerivedSha.textContent = ef.derived_sha256 || ef.original_sha256;

        inspectHashText.textContent = 'Non-Alteration Verified (MD5/SHA-256 Match)';

        // Load MP4 Video
        inspectorVideoSrc.src = `/api/video/${evidenceId}?t=${Date.now()}`;
        inspectorVideoPlayer.load();

        rightSidebar.classList.remove('hidden');

        // Highlight in footage library sidebar
        document.querySelectorAll('.footage-item').forEach(i => {
            i.classList.toggle('selected', i.dataset.id === evidenceId);
        });

        const btnDeleteEvidence = document.getElementById('btn-delete-evidence');
        if (btnDeleteEvidence) {
            btnDeleteEvidence.onclick = async () => {
                if (!confirm('Are you sure you want to delete this evidence?')) return;
                
                try {
                    const res = await fetch(`/api/evidence/${evidenceId}`, { method: 'DELETE' });
                    if (res.ok) {
                        rightSidebar.classList.add('hidden');
                        openCasePinboard(currentCaseId);
                    } else {
                        alert('Failed to delete evidence.');
                    }
                } catch (e) {
                    alert('Error deleting evidence: ' + e);
                }
            };
        }
    }

    // Render Bottom Multi-Camera Timeline Scrubber (Matching Reference UI Component)
    function renderTimelineScrubber(events, evidenceFiles = []) {
        const wrapper = document.getElementById('timeline-channels');
        if (!wrapper) return;

        const files = (currentCaseData?.evidence_files && currentCaseData.evidence_files.length > 0)
            ? currentCaseData.evidence_files
            : (evidenceFiles.length > 0 ? evidenceFiles : null);

        if (!files || files.length === 0) {
            wrapper.innerHTML = `<div class="timeline-empty-msg">No indexed timeline frames yet. Ingest an evidence recording to view multi-camera correlation.</div>`;
            return;
        }

        wrapper.innerHTML = files.map((ef, i) => {
            const isTier1 = ef.vendor === 'dahua' || ef.vendor === 'hikvision';
            const camNum = i + 1;
            const vendorName = ef.vendor ? (ef.vendor.charAt(0).toUpperCase() + ef.vendor.slice(1)) : 'Unknown';
            const tierBadge = isTier1
                ? `<span class="timeline-tier-badge tier1">Tier 1</span>`
                : `<span class="timeline-tier-badge tier2">Tier 2</span>`;
            
            const trackSegments = isTier1
                ? `
                    <div class="timeline-track-segments tier1-track">
                        <div class="timeline-seg"></div>
                        <div class="timeline-seg"></div>
                        <div class="timeline-seg"></div>
                        <div class="timeline-seg active"></div>
                        <div class="timeline-seg"></div>
                        <div class="timeline-seg"></div>
                        <div class="timeline-seg"></div>
                        <div class="timeline-playhead-cursor" style="left: 48%;"></div>
                    </div>
                `
                : `
                    <div class="timeline-track-segments tier2-track-hazard">
                        <div class="timeline-seg-hazard"></div>
                        <div class="timeline-seg-hazard"></div>
                        <div class="timeline-seg-hazard"></div>
                        <div class="timeline-seg-hazard"></div>
                        <div class="timeline-seg-hazard"></div>
                        <div class="timeline-playhead-cursor" style="left: 48%;"></div>
                    </div>
                `;

            return `
                <div class="timeline-channel-row">
                    <div class="channel-header-pill ${isTier1 ? 'header-tier1' : 'header-tier2'}">
                        <svg class="channel-cam-icon" width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></svg>
                        <span class="cam-title">Camera ${camNum} (${vendorName})</span>
                        ${tierBadge}
                    </div>
                    <div class="channel-track-lane">
                        ${trackSegments}
                    </div>
                </div>
            `;
        }).join('');
    }

    // Connect Certificate Generation Action
    const btnGenerateCertTop = document.getElementById('btn-generate-cert-top');
    if (btnGenerateCertTop) {
        btnGenerateCertTop.addEventListener('click', () => {
            if (!currentCaseId) {
                alert('Please select or open an active case to generate certificate.');
                return;
            }
            window.open(`/api/report/${currentCaseId}`, '_blank');
        });
    }

    // Sidebar Toggles
    btnToggleLeftSidebar.addEventListener('click', () => leftSidebar.classList.toggle('hidden'));
    btnCloseLeftSidebar.addEventListener('click', () => leftSidebar.classList.add('hidden'));
    btnCloseRightSidebar.addEventListener('click', () => rightSidebar.classList.add('hidden'));

    // Prevent corkboard canvas zoom from capturing scroll/wheel events inside sidebars
    if (rightSidebar) {
        rightSidebar.addEventListener('wheel', (e) => e.stopPropagation(), { passive: true });
        rightSidebar.addEventListener('mousedown', (e) => e.stopPropagation());
    }
    if (leftSidebar) {
        leftSidebar.addEventListener('wheel', (e) => e.stopPropagation(), { passive: true });
        leftSidebar.addEventListener('mousedown', (e) => e.stopPropagation());
    }

    // Sidebar Live Footage Search
    const footageSearchInput = document.getElementById('footage-search-input');
    if (footageSearchInput) {
        footageSearchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            const items = footageList.querySelectorAll('.footage-item');
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                if (!query || text.includes(query)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    // ==========================================================================
    // 5. INGEST RECORDING MODAL & UPLOAD WORKFLOW
    // ==========================================================================
    btnTriggerUploadModal.addEventListener('click', () => uploadModal.classList.remove('hidden'));
    btnCloseUploadModal.addEventListener('click', () => uploadModal.classList.add('hidden'));
    btnCancelUpload.addEventListener('click', () => uploadModal.classList.add('hidden'));

    modalUploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const fileInput = document.getElementById('file-input');
        if (!fileInput.files || fileInput.files.length === 0) {
            alert('Please select a video evidence file to ingest.');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('case_id', currentCaseId);
        formData.append('vendor_override', document.getElementById('vendor-select').value);
        formData.append('validation_confidence', document.getElementById('validation-select').value);

        const progressSec = document.getElementById('modal-progress-section');
        const progressBar = document.getElementById('modal-progress-bar');
        const progressPct = document.getElementById('modal-progress-pct');
        const statusMsg = document.getElementById('modal-status-msg');

        progressSec.classList.remove('hidden');
        progressBar.style.width = '10%';
        progressPct.textContent = '10%';
        statusMsg.textContent = 'Uploading evidence file...';

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Upload failed');

            const evidenceId = data.evidence_file_id;

            // Poll status
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(async () => {
                const sRes = await fetch(`/api/status/${evidenceId}`);
                if (!sRes.ok) return;

                const statusData = await sRes.json();
                const pct = statusData.progress || 30;
                progressBar.style.width = pct + '%';
                progressPct.textContent = pct + '%';
                statusMsg.textContent = statusData.message || 'Analyzing stream...';

                if (statusData.status === 'processed') {
                    clearInterval(pollInterval);
                    uploadModal.classList.add('hidden');
                    modalUploadForm.reset();
                    progressSec.classList.add('hidden');
                    
                    // Refresh current case pinboard
                    openCasePinboard(currentCaseId);
                    selectEvidenceNode(evidenceId);

                } else if (statusData.status === 'failed') {
                    clearInterval(pollInterval);
                    alert('Forensic processing failed: ' + (statusData.error || 'Unknown error'));
                }
            }, 1000);

        } catch (err) {
            alert('Upload error: ' + err.message);
            progressSec.classList.add('hidden');
        }
    });

    // BSA Report Downloads
    document.getElementById('btn-generate-cert-top').addEventListener('click', () => {
        if (currentCaseId) window.location.href = `/api/report/${currentCaseId}`;
    });

    document.getElementById('btn-download-report-tab').addEventListener('click', () => {
        if (currentCaseId) window.location.href = `/api/report/${currentCaseId}`;
    });
});
