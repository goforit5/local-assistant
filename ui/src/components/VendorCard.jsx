/**
 * VendorCard Component
 *
 * Displays vendor information with matched/created badge.
 * Shows vendor name, address, and confidence score.
 */

import React from 'react';
import './VendorCard.css';

const VendorCard = ({ vendor }) => {
  if (!vendor) {
    return null;
  }

  const { id, name, matched, confidence, tier, address, email } = vendor;

  // Format confidence as percentage
  const confidencePercent = confidence ? `${(confidence * 100).toFixed(0)}%` : null;

  // Determine badge color based on match status
  const badgeClass = matched ? 'badge-matched' : 'badge-created';
  const badgeText = matched ? 'Matched Existing' : 'Created New';

  return (
    <div className="vendor-card">
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">🏢</span>
          Vendor
        </h3>
        <span className={`badge ${badgeClass}`}>
          {badgeText}
        </span>
      </div>

      <div className="card-body">
        <div className="vendor-name">{name}</div>

        {address && (
          <div className="vendor-detail">
            <span className="label">Address:</span>
            <span className="value">{address}</span>
          </div>
        )}

        {email && (
          <div className="vendor-detail">
            <span className="label">Email:</span>
            <span className="value">{email}</span>
          </div>
        )}

        {matched && (
          <div className="vendor-detail">
            <span className="label">Match Confidence:</span>
            <span className="value confidence">
              {confidencePercent}
              {tier && ` (${tier})`}
            </span>
          </div>
        )}
      </div>

      <div className="card-footer">
        <a href={`/vendors/${id}`} className="link-button">
          View History →
        </a>
      </div>
    </div>
  );
};

export default VendorCard;
