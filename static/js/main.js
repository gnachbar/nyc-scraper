// NYC Events - JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize page functionality
    initializeFilters();
    initializeTableSorting();
    initializeSearchEnhancements();
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
