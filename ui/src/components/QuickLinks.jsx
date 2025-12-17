/**
 * QuickLinks Component
 *
 * Provides navigation links to related resources:
 * - Interaction timeline
 * - Vendor history
 * - Document download
 */

import React from 'react';
import './QuickLinks.css';

const QuickLinks = ({ links }) => {
  if (!links) {
    return null;
  }

  const { timeline, vendor, download } = links;

  return (
    <div className="quick-links-card">
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">🔗</span>
          Quick Links
        </h3>
      </div>

      <div className="card-body">
        <div className="links-grid">
          {timeline && (
            <a href={timeline} className="link-item timeline-link">
              <span className="link-icon">📅</span>
              <span className="link-text">
                <span className="link-title">Interaction Timeline</span>
                <span className="link-description">View complete audit trail</span>
              </span>
            </a>
          )}

          {vendor && (
            <a href={vendor} className="link-item vendor-link">
              <span className="link-icon">🏢</span>
              <span className="link-text">
                <span className="link-title">Vendor History</span>
                <span className="link-description">All documents & commitments</span>
              </span>
            </a>
          )}

          {download && (
            <a href={download} className="link-item download-link" download>
              <span className="link-icon">⬇️</span>
              <span className="link-text">
                <span className="link-title">Download PDF</span>
                <span className="link-description">Original document file</span>
              </span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
};

export default QuickLinks;
