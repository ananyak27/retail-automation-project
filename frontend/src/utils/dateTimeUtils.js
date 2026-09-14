/**
 * Formats an ISO date string or Date object into the user's device local timezone.
 * Format: "14 Sep 2026, 08:30 PM"
 */
export function formatDateTime(dateInput) {
  if (!dateInput) return 'N/A';
  
  try {
    let dateStr = String(dateInput).trim();
    // If naive ISO string from backend without timezone, append Z to force UTC parsing
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(dateStr)) {
      dateStr += 'Z';
    }
    
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'N/A';
    
    const day = date.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
    
    const time = date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
    
    return `${day}, ${time}`;
  } catch (e) {
    return 'N/A';
  }
}

