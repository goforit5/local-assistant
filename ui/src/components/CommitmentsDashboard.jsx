/**
 * CommitmentsDashboard Component
 *
 * Main dashboard with filters, sorting, and commitment list.
 */

import React, { useState } from 'react';
import CommitmentsList from './CommitmentsList';
import './CommitmentsDashboard.css';

const CommitmentsDashboard = ({
  commitments,
  loading,
  total,
  filters,
  onFilterChange,
  onFulfill,
  onRefresh,
}) => {
  const [sortBy, setSortBy] = useState('priority'); // priority or due_date

  // Handle filter changes
  const handleStateChange = (e) => {
    onFilterChange({ state: e.target.value || null });
  };

  const handleDomainChange = (e) => {
    onFilterChange({ domain: e.target.value || null });
  };

  const handlePriorityChange = (e) => {
    onFilterChange({ priority_min: parseInt(e.target.value) });
  };

  // Sort commitments
  const sortedCommitments = [...commitments].sort((a, b) => {
    if (sortBy === 'priority') {
      return b.priority - a.priority; // High to low
    } else {
      // Sort by due_date (nulls last)
      if (!a.due_date) return 1;
      if (!b.due_date) return -1;
      return new Date(a.due_date) - new Date(b.due_date);
    }
  });

  return (
    <div className="commitments-dashboard">
      {/* Filters Section */}
      <div className="filters-section">
        <h2 className="section-title">Filters</h2>

        <div className="filters-grid">
          {/* State Filter */}
          <div className="filter-group">
            <label htmlFor="state-filter" className="filter-label">
              State
            </label>
            <select
              id="state-filter"
              className="filter-select"
              value={filters.state || ''}
              onChange={handleStateChange}
            >
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="fulfilled">Fulfilled</option>
              <option value="canceled">Canceled</option>
              <option value="paused">Paused</option>
            </select>
          </div>

          {/* Domain Filter */}
          <div className="filter-group">
            <label htmlFor="domain-filter" className="filter-label">
              Domain
            </label>
            <select
              id="domain-filter"
              className="filter-select"
              value={filters.domain || ''}
              onChange={handleDomainChange}
            >
              <option value="">All</option>
              <option value="finance">Finance</option>
              <option value="legal">Legal</option>
              <option value="health">Health</option>
              <option value="personal">Personal</option>
              <option value="work">Work</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div className="filter-group">
            <label htmlFor="priority-filter" className="filter-label">
              Min Priority: {filters.priority_min}
            </label>
            <input
              id="priority-filter"
              type="range"
              className="filter-slider"
              min="0"
              max="100"
              step="10"
              value={filters.priority_min}
              onChange={handlePriorityChange}
            />
            <div className="slider-labels">
              <span>0</span>
              <span>50</span>
              <span>100</span>
            </div>
          </div>

          {/* Sort By */}
          <div className="filter-group">
            <label htmlFor="sort-filter" className="filter-label">
              Sort By
            </label>
            <select
              id="sort-filter"
              className="filter-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="priority">Priority (High to Low)</option>
              <option value="due_date">Due Date (Soonest First)</option>
            </select>
          </div>
        </div>

        {/* Results Count & Refresh */}
        <div className="filters-footer">
          <span className="results-count">
            {loading ? 'Loading...' : `${total} commitment${total !== 1 ? 's' : ''}`}
          </span>
          <button className="refresh-button" onClick={onRefresh} disabled={loading}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Commitments List */}
      <div className="commitments-section">
        <h2 className="section-title">Commitments</h2>

        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <span>Loading commitments...</span>
          </div>
        ) : commitments.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">📭</span>
            <h3>No Commitments Found</h3>
            <p>Try adjusting your filters or create a new commitment</p>
          </div>
        ) : (
          <CommitmentsList commitments={sortedCommitments} onFulfill={onFulfill} />
        )}
      </div>
    </div>
  );
};

export default CommitmentsDashboard;
