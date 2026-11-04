// Seeded defect for the review evals: do not fix.
// Returns page `page` (1-based) of `items`, `size` items per page.
function paginate(items, page, size) {
  const start = (page - 1) * size;
  const out = [];
  // SEEDED: CWE-193 off-by-one. `<=` returns size + 1 items per page.
  for (let i = start; i <= start + size && i < items.length; i++) {
    out.push(items[i]);
  }
  return out;
}

module.exports = { paginate };
