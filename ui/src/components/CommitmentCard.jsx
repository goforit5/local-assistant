/**
 * CommitmentCard Component
 *
 * Displays commitment with priority color coding and explainable reason.
 * Includes quick action button to mark as fulfilled.
 */

import React, { useState } from 'react';
import './CommitmentCard.css';

const CommitmentCard = ({ commitment, onFulfill }) => {
  const [fulfilling, setFulfilling] = useState(false);
  const [fulfilled, setFulfilled] = useState(false);

  if (!commitment) {
    return null;
  }

  const { id, title, priority, reason, due_date, commitment_type, state } = commitment;

  // Determine priority level and color
  const getPriorityLevel = (score) => {
    if (score >= 80) return { level: 'high', color: '#d32f2f', label: 'High' };
    if (score >= 50) return { level: 'medium', color: '#f57c00', label: 'Medium' };
    return { level: 'low', color: '#388e3c', label: 'Low' };
  };

  const priorityInfo = getPriorityLevel(priority);

  // Format due date
  const formatDueDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.ceil((date - now) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) return `Overdue by ${Math.abs(diffDays)} days`;
    if (diffDays === 0) return 'Due today';
    if (diffDays === 1) return 'Due tomorrow';
    if (diffDays <= 7) return `Due in ${diffDays} days`;
    return date.toLocaleDateString();
  };

  const dueText = formatDueDate(due_date);

  // Handle fulfill action
  const handleFulfill = async () => {
    if (fulfilling || fulfilled) return;

    setFulfilling(true);
    try {
      if (onFulfill) {
        await onFulfill(id);
      }
      setFulfilled(true);
    } catch (error) {
      console.error('Failed to fulfill commitment:', error);
      alert('Failed to mark as fulfilled');
    } finally {
      setFulfilling(false);
    }
  };

  const isActive = state === 'active' && !fulfilled;

  return (
    <div className={`commitment-card priority-${priorityInfo.level}`}>
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">📋</span>
          Commitment
        </h3>
        <span
          className="priority-badge"
          style={{ backgroundColor: priorityInfo.color }}
        >
          Priority: {priority}
        </span>
      </div>

      <div className="card-body">
        <div className="commitment-title">{title}</div>

        <div className="commitment-meta">
          <span className="meta-item">
            <span className="meta-label">Type:</span>
            <span className="meta-value">{commitment_type}</span>
          </span>

          <span className="meta-item">
            <span className="meta-label">State:</span>
            <span className={`meta-value state-${state}`}>
              {fulfilled ? 'fulfilled' : state}
            </span>
          </span>

          {dueText && (
            <span className="meta-item due-date">
              <span className="meta-label">Due:</span>
              <span className="meta-value">{dueText}</span>
            </span>
          )}
        </div>

        {reason && (
          <div className="commitment-reason">
            <span className="reason-label">Why it matters:</span>
            <p className="reason-text">{reason}</p>
          </div>
        )}
      </div>

      <div className="card-footer">
        {isActive && (
          <button
            className={`fulfill-button ${fulfilling ? 'fulfilling' : ''}`}
            onClick={handleFulfill}
            disabled={fulfilling}
          >
            {fulfilling ? 'Marking...' : '✓ Mark as Fulfilled'}
          </button>
        )}
        {(fulfilled || state === 'fulfilled') && (
          <div className="fulfilled-badge">✓ Fulfilled</div>
        )}
      </div>
    </div>
  );
};

export default CommitmentCard;
