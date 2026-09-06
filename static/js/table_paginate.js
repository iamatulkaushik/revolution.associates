/**
 * Client-side row pagination for long input/result tables.
 *
 * Usage:
 *   <table id="my-table"> ... <tbody> rows with class="paginate-row" ... </tbody></table>
 *   <div id="my-table-pager"></div>
 *   <script>paginateTable('my-table', 'my-table-pager', 10, 15);</script>
 *
 * - rowsPerPage: rows shown per page (default 10)
 * - threshold: pagination only activates if total rows exceed this (default 15)
 * - Rows hidden via display:none are NOT counted (so branch/search filters compose
 *   cleanly with pagination — call refreshPagination(tableId) after filtering).
 */
function paginateTable(tableId, pagerId, rowsPerPage, threshold) {
    rowsPerPage = rowsPerPage || 10;
    threshold = threshold || 15;

    const table = document.getElementById(tableId);
    const pager = document.getElementById(pagerId);
    if (!table || !pager) return;

    const state = { page: 1, rowsPerPage, threshold };
    table._paginateState = state;

    function getVisibleRows() {
        return Array.from(table.querySelectorAll('tbody tr.paginate-row'))
            .filter(r => r.dataset.filteredOut !== 'true');
    }

    function render() {
        const rows = getVisibleRows();
        const total = rows.length;

        if (total <= state.threshold) {
            rows.forEach(r => r.style.display = '');
            pager.innerHTML = '';
            return;
        }

        const totalPages = Math.ceil(total / state.rowsPerPage);
        if (state.page > totalPages) state.page = totalPages;
        if (state.page < 1) state.page = 1;

        const start = (state.page - 1) * state.rowsPerPage;
        const end = start + state.rowsPerPage;

        rows.forEach((r, i) => {
            r.style.display = (i >= start && i < end) ? '' : 'none';
        });

        let html = '<div class="pager-controls" style="display:flex;align-items:center;gap:8px;margin:10px 0;flex-wrap:wrap;">';
        html += `<button type="button" class="button" ${state.page === 1 ? 'disabled' : ''} onclick="_paginateGo('${tableId}','${pagerId}',1)">&laquo; First</button>`;
        html += `<button type="button" class="button" ${state.page === 1 ? 'disabled' : ''} onclick="_paginateGo('${tableId}','${pagerId}',${state.page - 1})">&lsaquo; Prev</button>`;
        html += `<span style="margin:0 6px;">Page ${state.page} of ${totalPages} (${total} rows)</span>`;
        html += `<button type="button" class="button" ${state.page === totalPages ? 'disabled' : ''} onclick="_paginateGo('${tableId}','${pagerId}',${state.page + 1})">Next &rsaquo;</button>`;
        html += `<button type="button" class="button" ${state.page === totalPages ? 'disabled' : ''} onclick="_paginateGo('${tableId}','${pagerId}',${totalPages})">Last &raquo;</button>`;
        html += '</div>';
        pager.innerHTML = html;
    }

    table._paginateRender = render;
    render();
}

function _paginateGo(tableId, pagerId, page) {
    const table = document.getElementById(tableId);
    if (!table || !table._paginateState) return;
    table._paginateState.page = page;
    table._paginateRender();
}

/** Call after client-side filtering (e.g. branch dropdown) changes row visibility,
 *  by setting row.dataset.filteredOut = 'true'/'false' BEFORE calling this. */
function refreshPagination(tableId) {
    const table = document.getElementById(tableId);
    if (table && table._paginateState) {
        table._paginateState.page = 1;
        table._paginateRender();
    }
}
