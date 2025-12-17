/**
 * ExtractionCard Component
 *
 * Displays extraction details including cost, model, and processing time.
 * Provides quick link to download original PDF.
 */

import React from 'react';
import './ExtractionCard.css';

const ExtractionCard = ({ extraction, documentId }) => {
  if (!extraction) {
    return null;
  }

  const { cost, model, pages_processed, duration_seconds } = extraction;

  // Format cost to 4 decimal places
  const formattedCost = cost ? `$${cost.toFixed(4)}` : 'N/A';

  // Format duration
  const formattedDuration = duration_seconds
    ? `${duration_seconds.toFixed(2)}s`
    : null;

  return (
    <div className="extraction-card">
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">🔍</span>
          Extraction Details
        </h3>
      </div>

      <div className="card-body">
        <div className="extraction-grid">
          <div className="extraction-item">
            <span className="item-label">Model</span>
            <span className="item-value model-value">{model}</span>
          </div>

          <div className="extraction-item">
            <span className="item-label">Cost</span>
            <span className="item-value cost-value">{formattedCost}</span>
          </div>

          <div className="extraction-item">
            <span className="item-label">Pages</span>
            <span className="item-value">{pages_processed}</span>
          </div>

          {formattedDuration && (
            <div className="extraction-item">
              <span className="item-label">Duration</span>
              <span className="item-value">{formattedDuration}</span>
            </div>
          )}
        </div>

        {/* Cost breakdown explanation */}
        <div className="cost-info">
          <span className="info-icon">ℹ️</span>
          <span className="info-text">
            Vision API cost for {pages_processed} page{pages_processed !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {documentId && (
        <div className="card-footer">
          <a
            href={`/api/documents/${documentId}/download`}
            className="download-button"
            download
          >
            ⬇️ Download Original PDF
          </a>
        </div>
      )}
    </div>
  );
};

export default ExtractionCard;
