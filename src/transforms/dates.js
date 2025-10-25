// Function to convert date format from "THURSDAY, OCTOBER 16" to "10/16/2024"
export function convertToMMDDYYYY(dateString, year = null) {
  const monthMap = {
    'JANUARY': '01', 'FEBRUARY': '02', 'MARCH': '03', 'APRIL': '04',
    'MAY': '05', 'JUNE': '06', 'JULY': '07', 'AUGUST': '08',
    'SEPTEMBER': '09', 'OCTOBER': '10', 'NOVEMBER': '11', 'DECEMBER': '12'
  };
  
  // Handle BAM date formats like "Oct 21—Oct 25, 2025" or "Sat, Nov 15, 2025"
  if (dateString.includes('—') || dateString.includes(',')) {
    // Extract the first date from ranges like "Oct 21—Oct 25, 2025"
    const firstDateMatch = dateString.match(/([A-Za-z]{3})\s+(\d{1,2})/);
    if (firstDateMatch) {
      const monthName = firstDateMatch[1].toUpperCase();
      const day = firstDateMatch[2];
      
      // Map abbreviated month names
      const abbrevMonthMap = {
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
      };
      
      if (abbrevMonthMap[monthName]) {
        const targetYear = year || new Date().getFullYear();
        return `${abbrevMonthMap[monthName]}/${day.padStart(2, '0')}/${targetYear}`;
      }
    }
  }
  
  // Handle Kings Theatre format: "THURSDAY, OCTOBER 16"
  const parts = dateString.split(', ');
  if (parts.length >= 2) {
    const monthDay = parts[1].split(' ');
    const month = monthDay[0];
    const day = monthDay[1];
    
    if (monthMap[month] && day) {
      const targetYear = year || new Date().getFullYear();
      return `${monthMap[month]}/${day.padStart(2, '0')}/${targetYear}`;
    }
  }
  
  // Fallback to original date if parsing fails
  return dateString;
}

// Helper function to get weeks in a month (pure version)
export function getWeeksInMonth(month, year) {
  // This is a simplified implementation - in practice, you'd need to analyze the calendar
  // to determine the actual weeks. For now, we'll assume 4-5 weeks per month.
  const weeks = [];
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  
  let currentWeekStart = new Date(firstDay);
  
  while (currentWeekStart <= lastDay) {
    const weekEnd = new Date(currentWeekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    
    if (weekEnd > lastDay) {
      weekEnd.setTime(lastDay.getTime());
    }
    
    weeks.push({
      startDate: currentWeekStart.toISOString().split('T')[0],
      endDate: weekEnd.toISOString().split('T')[0]
    });
    
    currentWeekStart.setDate(currentWeekStart.getDate() + 7);
  }
  
  return weeks;
}
