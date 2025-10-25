import fs from 'fs';

// Read the JSON file
const events = JSON.parse(fs.readFileSync('kings_theatre_events.json', 'utf8'));

// Create CSV header
const csvHeader = 'Event Name,Event Date,Event Time,Event Location,Event URL\n';

// Convert each event to CSV row
const csvRows = events.map(event => {
  // Escape commas and quotes in the data
  const escapeCsv = (str) => {
    if (str === undefined || str === null) return '';
    return `"${String(str).replace(/"/g, '""')}"`;
  };
  
  return [
    escapeCsv(event.eventName),
    escapeCsv(event.eventDate),
    escapeCsv(event.eventTime || ''),
    escapeCsv(event.eventLocation),
    escapeCsv(event.eventUrl)
  ].join(',');
});

// Combine header and rows
const csvContent = csvHeader + csvRows.join('\n');

// Write to CSV file
fs.writeFileSync('kings_theatre_events.csv', csvContent);

console.log(`✅ Successfully converted ${events.length} events to CSV format`);
console.log(`📁 CSV file saved as: kings_theatre_events.csv`);
console.log(`\n📊 Summary:`);
console.log(`- Total events: ${events.length}`);
console.log(`- Events with dates: ${events.filter(e => e.eventDate && e.eventDate !== 'undefined').length}`);
console.log(`- Events with times: ${events.filter(e => e.eventTime && e.eventTime !== 'undefined').length}`);
console.log(`- Events with URLs: ${events.filter(e => e.eventUrl && e.eventUrl !== 'undefined').length}`);

// Show first few rows as preview
console.log(`\n🔍 First 5 events preview:`);
events.slice(0, 5).forEach((event, index) => {
  console.log(`${index + 1}. ${event.eventName}`);
  console.log(`   Date: ${event.eventDate || 'N/A'}`);
  console.log(`   Time: ${event.eventTime || 'N/A'}`);
  console.log(`   Location: ${event.eventLocation}`);
  console.log(`   URL: ${event.eventUrl}`);
  console.log('');
});
