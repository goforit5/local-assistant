/**
 * CommitmentsList Component
 *
 * Renders a list of commitment cards.
 */

import React from 'react';
import CommitmentCard from './CommitmentCard';
import './CommitmentsList.css';

const CommitmentsList = ({ commitments, onFulfill }) => {
  if (!commitments || commitments.length === 0) {
    return null;
  }

  return (
    <div className="commitments-list">
      {commitments.map((commitment) => (
        <CommitmentCard
          key={commitment.id}
          commitment={commitment}
          onFulfill={onFulfill}
        />
      ))}
    </div>
  );
};

export default CommitmentsList;
