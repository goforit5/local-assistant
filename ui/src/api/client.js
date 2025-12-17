/**
 * API Client
 *
 * Centralized API communication functions for Life Graph Integration.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Upload document and process through pipeline
 * @param {File} file - Document file to upload
 * @param {string} extractionType - Type of extraction (invoice, receipt, etc.)
 * @returns {Promise<object>} - Complete entity graph
 */
export async function uploadDocument(file, extractionType = 'invoice') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('extraction_type', extractionType);

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

/**
 * Get document details by ID
 * @param {string} documentId - Document UUID
 * @returns {Promise<object>} - Document details
 */
export async function getDocument(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get document');
  }

  return response.json();
}

/**
 * Download document file
 * @param {string} documentId - Document UUID
 * @returns {Promise<Blob>} - Document file blob
 */
export async function downloadDocument(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/download`);

  if (!response.ok) {
    throw new Error('Failed to download document');
  }

  return response.blob();
}

/**
 * List vendors with optional search
 * @param {object} params - Query parameters { query, offset, limit }
 * @returns {Promise<object>} - Vendor list response
 */
export async function listVendors(params = {}) {
  const queryParams = new URLSearchParams(params);
  const response = await fetch(`${API_BASE_URL}/api/vendors?${queryParams}`);

  if (!response.ok) {
    throw new Error('Failed to list vendors');
  }

  return response.json();
}

/**
 * Get vendor details by ID
 * @param {string} vendorId - Vendor UUID
 * @returns {Promise<object>} - Vendor details with stats
 */
export async function getVendor(vendorId) {
  const response = await fetch(`${API_BASE_URL}/api/vendors/${vendorId}`);

  if (!response.ok) {
    throw new Error('Failed to get vendor');
  }

  return response.json();
}

/**
 * Get vendor documents
 * @param {string} vendorId - Vendor UUID
 * @returns {Promise<object>} - Vendor documents
 */
export async function getVendorDocuments(vendorId) {
  const response = await fetch(`${API_BASE_URL}/api/vendors/${vendorId}/documents`);

  if (!response.ok) {
    throw new Error('Failed to get vendor documents');
  }

  return response.json();
}

/**
 * List commitments with filters
 * @param {object} params - Query parameters { state, domain, priority_min, due_before, offset, limit }
 * @returns {Promise<object>} - Commitment list response
 */
export async function listCommitments(params = {}) {
  const queryParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      queryParams.append(key, value);
    }
  });

  const response = await fetch(`${API_BASE_URL}/api/commitments?${queryParams}`);

  if (!response.ok) {
    throw new Error('Failed to list commitments');
  }

  return response.json();
}

/**
 * Get commitment details by ID
 * @param {string} commitmentId - Commitment UUID
 * @returns {Promise<object>} - Commitment details
 */
export async function getCommitment(commitmentId) {
  const response = await fetch(`${API_BASE_URL}/api/commitments/${commitmentId}`);

  if (!response.ok) {
    throw new Error('Failed to get commitment');
  }

  return response.json();
}

/**
 * Mark commitment as fulfilled
 * @param {string} commitmentId - Commitment UUID
 * @returns {Promise<object>} - Updated commitment
 */
export async function fulfillCommitment(commitmentId) {
  const response = await fetch(`${API_BASE_URL}/api/commitments/${commitmentId}/fulfill`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fulfill commitment');
  }

  return response.json();
}

/**
 * Update commitment
 * @param {string} commitmentId - Commitment UUID
 * @param {object} updateData - Fields to update
 * @returns {Promise<object>} - Updated commitment
 */
export async function updateCommitment(commitmentId, updateData) {
  const response = await fetch(`${API_BASE_URL}/api/commitments/${commitmentId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updateData),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update commitment');
  }

  return response.json();
}

/**
 * Get interaction timeline
 * @param {object} params - Query parameters { entity_type, entity_id, interaction_type, date_from, date_to, offset, limit }
 * @returns {Promise<object>} - Timeline response
 */
export async function getTimeline(params = {}) {
  const queryParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      queryParams.append(key, value);
    }
  });

  const response = await fetch(`${API_BASE_URL}/api/interactions/timeline?${queryParams}`);

  if (!response.ok) {
    throw new Error('Failed to get timeline');
  }

  return response.json();
}

/**
 * Export interactions
 * @param {string} format - Export format (csv or json)
 * @param {object} params - Query parameters { date_from, date_to, interaction_type, entity_type }
 * @returns {Promise<Blob>} - Export file blob
 */
export async function exportInteractions(format = 'csv', params = {}) {
  const queryParams = new URLSearchParams({ format, ...params });
  const response = await fetch(`${API_BASE_URL}/api/interactions/export?${queryParams}`);

  if (!response.ok) {
    throw new Error('Failed to export interactions');
  }

  return response.blob();
}
