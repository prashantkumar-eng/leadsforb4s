import React, { useState } from 'react';

/**
 * Scholarship Outreach Dashboard
 *
 * This React component provides a simple interface to extract contact
 * information from university faculty/department pages.  Users paste a URL
 * into the input field and press the “Fetch Contacts” button.  The app
 * sends a POST request to the Flask backend (running on port 5000) and
 * displays the extracted contacts in a table.  Each row shows the name,
 * designation, department (where available), email and phone.  A
 * “Lead Status” dropdown lets users mark each lead as New, Contacted or
 * Partnered.  The “Download CSV” button exports the current table into a
 * comma‑separated file for offline use.
 */
export default function App() {
  const [url, setUrl] = useState('');
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Update a contact's lead status in the state
  const updateStatus = (index, status) => {
    setContacts((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], status };
      return next;
    });
  };

  // Convert contacts to CSV and trigger download
  const downloadCsv = () => {
    if (!contacts.length) return;
    const header = ['Name', 'Designation', 'Department', 'Email', 'Phone', 'Lead Status'];
    const rows = contacts.map((c) => [
      c.name ?? '',
      c.designation ?? '',
      c.department ?? '',
      c.email ?? '',
      c.phone ?? '',
      c.status ?? 'New',
    ]);
    const csvContent = [header, ...rows]
      .map((row) => row.map((field) => `"${String(field).replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const urlBlob = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = urlBlob;
    link.setAttribute('download', 'contacts.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Send the URL to the backend and process the response
  const fetchContacts = async () => {
    if (!url) return;
    setLoading(true);
    setError(null);
    setContacts([]);
    try {
      const res = await fetch('http://localhost:5000/api/extract', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to fetch contacts');
      }
      // Attach default lead status to each contact
      const withStatus = data.map((item) => ({ ...item, status: 'New' }));
      setContacts(withStatus);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-6 bg-gray-100">
      <h1 className="text-3xl font-semibold text-primary mb-4">Scholarship Outreach Dashboard</h1>
      <div className="flex flex-col md:flex-row items-start md:items-end mb-6 space-y-4 md:space-y-0 md:space-x-4">
        <div className="flex-1">
          <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-1">
            College faculty/department page URL
          </label>
          <input
            id="url"
            type="text"
            className="w-full border border-gray-300 rounded-md py-2 px-3 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            placeholder="https://www.example.edu/faculty"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
        <button
          onClick={fetchContacts}
          className="inline-flex items-center justify-center px-6 py-2 bg-primary text-white font-medium rounded-md hover:bg-primary-light focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={loading || !url}
        >
          {loading ? 'Loading…' : 'Fetch Contacts'}
        </button>
        <button
          onClick={downloadCsv}
          className="inline-flex items-center justify-center px-6 py-2 bg-secondary text-white font-medium rounded-md hover:bg-blue-600 focus:outline-none"
          disabled={!contacts.length}
        >
          Download CSV
        </button>
      </div>
      {error && <div className="text-red-600 mb-4">Error: {error}</div>}
      <div className="overflow-x-auto">
        <table className="min-w-full bg-white shadow-sm rounded-lg overflow-hidden">
          <thead className="bg-primary text-white">
            <tr>
              <th className="px-4 py-2 text-left">Name</th>
              <th className="px-4 py-2 text-left">Designation</th>
              <th className="px-4 py-2 text-left">Department</th>
              <th className="px-4 py-2 text-left">Email</th>
              <th className="px-4 py-2 text-left">Phone</th>
              <th className="px-4 py-2 text-left">Lead Status</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((contact, idx) => (
              <tr key={`${contact.name}-${idx}`} className={idx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                <td className="px-4 py-2 whitespace-nowrap">{contact.name}</td>
                <td className="px-4 py-2 whitespace-nowrap">{contact.designation}</td>
                <td className="px-4 py-2 whitespace-nowrap">{contact.department || '-'}</td>
                <td className="px-4 py-2 whitespace-nowrap">
                  {contact.email ? (
                    <a href={`mailto:${contact.email}`} className="text-blue-600 hover:underline">
                      {contact.email}
                    </a>
                  ) : (
                    '-'
                  )}
                </td>
                <td className="px-4 py-2 whitespace-nowrap">
                  {contact.phone ? (
                    <a href={`tel:${contact.phone}`} className="text-blue-600 hover:underline">
                      {contact.phone}
                    </a>
                  ) : (
                    '-'
                  )}
                </td>
                <td className="px-4 py-2 whitespace-nowrap">
                  <select
                    className="border border-gray-300 rounded-md py-1 px-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary"
                    value={contact.status}
                    onChange={(e) => updateStatus(idx, e.target.value)}
                  >
                    <option value="New">New</option>
                    <option value="Contacted">Contacted</option>
                    <option value="Partnered">Partnered</option>
                  </select>
                </td>
              </tr>
            ))}
            {!contacts.length && !loading && (
              <tr>
                <td colSpan="6" className="px-4 py-6 text-center text-gray-500">
                  No contacts to display.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}