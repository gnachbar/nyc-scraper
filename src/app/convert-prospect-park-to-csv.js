import fs from 'fs';

// Read the JSON file
const jsonData = JSON.parse(fs.readFileSync('prospect_park_events.json', 'utf8'));

// Convert to CSV
const csvHeader = 'Event Name,Event Date,Event Time,Event Location,Event URL\n';

const csvRows = jsonData.map(event => {
  // Escape commas and quotes in the data
  const escapeCsv = (str) => {
    if (str === null || str === undefined) return '';
    return `"${str.toString().replace(/"/g, '""')}"`;
  };

  return [
    escapeCsv(event.eventName),
    escapeCsv(event.eventDate),
    escapeCsv(event.eventTime || ''),
    escapeCsv(event.eventLocation),
    escapeCsv(event.eventUrl)
  ].join(',');
});

const csvContent = csvHeader + csvRows.join('\n');

// Write to CSV file
fs.writeFileSync('prospect_park_events.csv', csvContent);

console.log(`Successfully converted ${jsonData.length} events to CSV`);
console.log('CSV file saved as: prospect_park_events.csv');
