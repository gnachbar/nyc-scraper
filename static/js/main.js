// NYC Events - JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize page functionality
	initializeSidebarToggle();
    initializeFilters();
    initializeTableSorting();
    initializeSearchEnhancements();
    initializeDateRangePicker();
    initializeTimeFilter();
});

// Filter functionality enhancements
function initializeFilters() {
    const filterForm = document.querySelector('.filters form');
    if (!filterForm) return;

    // Auto-submit form when filters change (with debounce)
    const inputs = filterForm.querySelectorAll('input, select');
    let debounceTimer;

    inputs.forEach(input => {
        input.addEventListener('change', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                filterForm.submit();
            }, 500); // 500ms delay
        });
    });

    // Clear filters button
    addClearFiltersButton();
}

// Initialize single date-range picker using Flatpickr
function initializeDateRangePicker() {
    const input = document.getElementById('date-range');
    const form = document.querySelector('.filter-form');
    if (!input || !form || typeof flatpickr === 'undefined') return;

    const hiddenStart = document.getElementById('date_start_hidden');
    const hiddenEnd = document.getElementById('date_end_hidden');
    let suppressNextChange = false; // guard to ignore change events we trigger programmatically

    // Compute default dates
    const defaultDates = [];
    const startVal = input.getAttribute('data-start');
    const endVal = input.getAttribute('data-end');
    if (startVal) defaultDates.push(startVal);
    if (endVal) defaultDates.push(endVal);

    const fp = flatpickr(input, {
        mode: 'range',
        dateFormat: 'Y-m-d',
        defaultDate: defaultDates,
        allowInput: false,
        closeOnSelect: false,
        onOpen: function() {
            // Reset selection each time the calendar opens
            suppressNextChange = true;
            try { this.clear(); } catch (_) {}
            hiddenStart.value = '';
            hiddenEnd.value = '';
        },
        onChange: function(selectedDates, dateStr) {
            if (suppressNextChange) {
                // Skip the change event caused by our programmatic clear on open
                suppressNextChange = false;
                return;
            }
            // selectedDates length: 0,1,2
            if (selectedDates.length === 0) {
                hiddenStart.value = '';
                hiddenEnd.value = '';
            } else if (selectedDates.length === 1) {
                hiddenStart.value = formatYMD(selectedDates[0]);
                hiddenEnd.value = '';
            } else if (selectedDates.length >= 2) {
                // Ensure chronological order
                const d0 = selectedDates[0];
                const d1 = selectedDates[1];
                const sameDay = d0.getFullYear() === d1.getFullYear() && d0.getMonth() === d1.getMonth() && d0.getDate() === d1.getDate();
                if (sameDay) {
                    const ymd = formatYMD(d0);
                    hiddenStart.value = ymd;
                    hiddenEnd.value = ymd; // treat as single-day range explicitly
                } else {
                    const a = d0 < d1 ? d0 : d1;
                    const b = d0 < d1 ? d1 : d0;
                    hiddenStart.value = formatYMD(a);
                    hiddenEnd.value = formatYMD(b);
                }
                // Submit only when two dates are selected
                clearTimeout(initializeDateRangePicker._t);
                initializeDateRangePicker._t = setTimeout(() => form.submit(), 200);
            }
        },
        onClose: function(selectedDates) {
            // If user closes after selecting only one date, treat as single-day
            if (selectedDates && selectedDates.length === 1) {
                const ymd = formatYMD(selectedDates[0]);
                hiddenStart.value = ymd;
                hiddenEnd.value = ymd;
                clearTimeout(initializeDateRangePicker._t);
                initializeDateRangePicker._t = setTimeout(() => form.submit(), 50);
            }
        }
    });
}

// Sidebar toggle for left-hand filters
function initializeSidebarToggle() {
	const sidebar = document.querySelector('.sidebar');
	const toggles = document.querySelectorAll('.sidebar-toggle');
	const expandBtn = document.querySelector('.sidebar-expand-btn');
	if (!sidebar || toggles.length === 0) return;

	// Restore state - default to open (null or undefined means open)
	try {
		const saved = localStorage.getItem('sidebar-collapsed');
		if (saved === 'true') {
			sidebar.classList.add('collapsed');
		} else {
			sidebar.classList.remove('collapsed');
		}
	} catch (_) {
		// Default to open if localStorage fails
		sidebar.classList.remove('collapsed');
	}

	const update = () => {
		const isCollapsed = sidebar.classList.contains('collapsed');
		toggles.forEach(toggle => {
			toggle.setAttribute('aria-expanded', String(!isCollapsed));
		});
		if (expandBtn) {
			expandBtn.setAttribute('aria-expanded', String(!isCollapsed));
		}
		try { localStorage.setItem('sidebar-collapsed', String(isCollapsed)); } catch (_) {}
	};

	const toggleSidebar = (e) => {
		if (e) e.stopPropagation();
		sidebar.classList.toggle('collapsed');
		update();
	};

	// Handle toggle buttons (X buttons)
	toggles.forEach(toggle => {
		toggle.addEventListener('click', toggleSidebar);
	});

	// Handle expand button
	if (expandBtn) {
		expandBtn.addEventListener('click', toggleSidebar);
	}

	update();
}

function formatYMD(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

// Add clear filters functionality
function addClearFiltersButton() {
    const filterForm = document.querySelector('.filters form');
    if (!filterForm) return;

    const clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.textContent = 'Clear Filters';
    clearButton.className = 'clear-filters-btn';
    clearButton.style.cssText = 'background: #6c757d; margin-left: 10px;';
    
    clearButton.addEventListener('click', function() {
        // Clear all form inputs
        const inputs = filterForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            if (input.type === 'text' || input.type === 'date') {
                input.value = '';
            } else if (input.tagName === 'SELECT') {
                input.selectedIndex = 0;
            }
        });
        
        // Submit form to show all events
        filterForm.submit();
    });

    // Add button to the filter row
    const filterRow = filterForm.querySelector('.filter-row:last-child');
    if (filterRow) {
        const buttonGroup = filterRow.querySelector('.filter-group:last-child');
        if (buttonGroup) {
            buttonGroup.appendChild(clearButton);
        }
    }
}

// Table sorting functionality
function initializeTableSorting() {
    const table = document.querySelector('.events-table');
    if (!table) return;

    const headers = table.querySelectorAll('th');
    headers.forEach((header, index) => {
        // Skip the Link column (last column)
        if (index === headers.length - 1) return;

        header.style.cursor = 'pointer';
        header.style.userSelect = 'none';
        header.innerHTML += ' <span class="sort-indicator">↕</span>';

        header.addEventListener('click', function() {
            sortTable(table, index);
        });
    });
}

// Sort table by column
function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Determine sort direction
    const isAscending = !table.dataset.sortAscending || table.dataset.sortColumn !== columnIndex.toString();
    table.dataset.sortAscending = isAscending;
    table.dataset.sortColumn = columnIndex.toString();

    // Sort rows
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        
        // Handle date sorting
        if (columnIndex === 1) { // Date column
            const aDate = parseDate(aText);
            const bDate = parseDate(bText);
            return isAscending ? aDate - bDate : bDate - aDate;
        }
        
        // Handle time sorting
        if (columnIndex === 2) { // Time column
            const aTime = parseTime(aText);
            const bTime = parseTime(bText);
            return isAscending ? aTime - bTime : bTime - aTime;
        }
        
        // Text sorting
        return isAscending ? aText.localeCompare(bText) : bText.localeCompare(aText);
    });

    // Update sort indicators
    updateSortIndicators(table, columnIndex, isAscending);

    // Reorder rows in DOM
    rows.forEach(row => tbody.appendChild(row));
}

// Update sort indicators
function updateSortIndicators(table, columnIndex, isAscending) {
    const headers = table.querySelectorAll('th');
    headers.forEach((header, index) => {
        const indicator = header.querySelector('.sort-indicator');
        if (index === columnIndex) {
            indicator.textContent = isAscending ? '↑' : '↓';
        } else {
            indicator.textContent = '↕';
        }
    });
}

// Parse date for sorting (MM/DD/YY format)
function parseDate(dateStr) {
    if (!dateStr || dateStr === '-') return 0;
    const parts = dateStr.split('/');
    if (parts.length !== 3) return 0;
    const year = 2000 + parseInt(parts[2]);
    const month = parseInt(parts[0]) - 1;
    const day = parseInt(parts[1]);
    return new Date(year, month, day).getTime();
}

// Parse time for sorting (HH:MM AM/PM format)
function parseTime(timeStr) {
    if (!timeStr || timeStr === '-') return 0;
    const [time, period] = timeStr.split(' ');
    const [hours, minutes] = time.split(':');
    let hour24 = parseInt(hours);
    if (period === 'PM' && hour24 !== 12) hour24 += 12;
    if (period === 'AM' && hour24 === 12) hour24 = 0;
    return hour24 * 60 + parseInt(minutes);
}

// Search enhancements
function initializeSearchEnhancements() {
    const searchInput = document.querySelector('input[name="search"]');
    if (!searchInput) return;

    // Add search suggestions (if we had more data)
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        if (query.length < 2) return;

        // Highlight matching text in table
        highlightSearchResults(query);
    });

    // Clear search highlighting when search is cleared
    searchInput.addEventListener('blur', function() {
        if (!this.value) {
            clearSearchHighlighting();
        }
    });
}

// Highlight search results in table
function highlightSearchResults(query) {
    const table = document.querySelector('.events-table');
    if (!table) return;

    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        const eventName = row.cells[0].textContent.toLowerCase();
        const venue = row.cells[3].textContent.toLowerCase();
        
        if (eventName.includes(query) || venue.includes(query)) {
            row.style.backgroundColor = '#fff3cd';
        } else {
            row.style.backgroundColor = '';
        }
    });
}

// Clear search highlighting
function clearSearchHighlighting() {
    const table = document.querySelector('.events-table');
    if (!table) return;

    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        row.style.backgroundColor = '';
    });
}

// Utility function to format dates
function formatDate(date) {
    const options = { 
        year: '2-digit', 
        month: '2-digit', 
        day: '2-digit' 
    };
    return date.toLocaleDateString('en-US', options);
}

// Utility function to format times
function formatTime(date) {
    const options = { 
        hour: 'numeric', 
        minute: '2-digit',
        hour12: true 
    };
    return date.toLocaleTimeString('en-US', options);
}

// Initialize time/distance filter with slider and toggle pills
function initializeTimeFilter() {
    const timeSlider = document.getElementById('time-slider');
    const timeValue = document.getElementById('time-value');
    const maxTimeHidden = document.getElementById('max_time_hidden');
    const modesHidden = document.getElementById('modes_hidden');
    const form = document.querySelector('.filter-form');
    const togglePills = document.querySelectorAll('.toggle-pill');
    
    if (!timeSlider || !timeValue || !maxTimeHidden || !modesHidden || !form) return;
    
    // Restore active state from URL params
    const currentModes = modesHidden.value || 'walk,subway,drive';
    const modeList = currentModes.split(',').map(m => m.trim().toLowerCase());
    
    togglePills.forEach(pill => {
        const mode = pill.getAttribute('data-mode').toLowerCase();
        if (modeList.includes(mode)) {
            pill.classList.add('active');
        }
    });
    
    // Handle slider movement
    timeSlider.addEventListener('input', function() {
        timeValue.textContent = this.value;
        maxTimeHidden.value = this.value;
    });
    
    // Handle slider release with debounce
    let sliderDebounce;
    timeSlider.addEventListener('change', function() {
        clearTimeout(sliderDebounce);
        sliderDebounce = setTimeout(() => {
            form.submit();
        }, 300);
    });
    
    // Handle toggle pill clicks
    togglePills.forEach(pill => {
        pill.addEventListener('click', function() {
            this.classList.toggle('active');
            updateModesInput();
            
            // Submit form when pills are toggled
            clearTimeout(sliderDebounce);
            sliderDebounce = setTimeout(() => {
                form.submit();
            }, 200);
        });
    });
    
    // Update the hidden modes input based on active pills
    function updateModesInput() {
        const activeModes = Array.from(togglePills)
            .filter(pill => pill.classList.contains('active'))
            .map(pill => pill.getAttribute('data-mode').toLowerCase());
        
        modesHidden.value = activeModes.join(',');
        
        // If no modes selected, default to all
        if (activeModes.length === 0) {
            modesHidden.value = 'walk,subway,drive';
            togglePills.forEach(pill => pill.classList.add('active'));
        }
    }
}
