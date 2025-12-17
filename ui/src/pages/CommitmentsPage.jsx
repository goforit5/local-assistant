/**
 * CommitmentsPage Component
 *
 * Main page for commitments dashboard with filtering, sorting, and management.
 */

import React, { useState, useEffect } from 'react';
import { listCommitments, fulfillCommitment } from '../api/client';
import CommitmentsDashboard from '../components/CommitmentsDashboard';
import './CommitmentsPage.css';

const CommitmentsPage = () => {
  const [commitments, setCommitments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    state: 'active',
    domain: null,
    priority_min: 0,
  });
  const [total, setTotal] = useState(0);

  // Load commitments
  useEffect(() => {
    loadCommitments();
  }, [filters]);

  const loadCommitments = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = {};
      if (filters.state) params.state = filters.state;
      if (filters.domain) params.domain = filters.domain;
      if (filters.priority_min > 0) params.priority_min = filters.priority_min;

      const response = await listCommitments(params);
      setCommitments(response.commitments);
      setTotal(response.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Handle filter changes
  const handleFilterChange = (newFilters) => {
    setFilters({ ...filters, ...newFilters });
  };

  // Handle fulfill action
  const handleFulfill = async (commitmentId) => {
    try {
      await fulfillCommitment(commitmentId);
      // Reload commitments
      await loadCommitments();
    } catch (err) {
      throw err; // Let the card handle the error
    }
  };

  return (
    <div className="commitments-page">
      <header className="page-header">
        <h1 className="page-title">📋 Commitments Dashboard</h1>
        <p className="page-subtitle">
          Manage your obligations, goals, and appointments
        </p>
      </header>

      {error && (
        <div className="error-banner">
          <span className="error-icon">⚠️</span>
          <span className="error-message">{error}</span>
          <button className="retry-button" onClick={loadCommitments}>
            Retry
          </button>
        </div>
      )}

      <CommitmentsDashboard
        commitments={commitments}
        loading={loading}
        total={total}
        filters={filters}
        onFilterChange={handleFilterChange}
        onFulfill={handleFulfill}
        onRefresh={loadCommitments}
      />
    </div>
  );
};

export default CommitmentsPage;
