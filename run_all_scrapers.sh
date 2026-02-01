#!/bin/bash
# Run all production scrapers and track results

SCRAPERS=(
  barclays_center
  bell_house
  bric_house
  brooklyn_library
  brooklyn_museum
  brooklyn_paramount
  concerts_on_the_slope
  crown_hill_theatre
  farm_one
  kings_theatre
  lepistol
  littlefield
  msg_calendar
  prospect_park
  public_records
  public_theater
  roulette
  shapeshifter_plus
  soapbox_gallery
)

PASSED=()
FAILED=()

echo "=============================================="
echo "Running all ${#SCRAPERS[@]} production scrapers"
echo "=============================================="
echo ""

for scraper in "${SCRAPERS[@]}"; do
  echo ">>> Running: $scraper"
  START=$(date +%s)

  if node "src/scrapers/${scraper}.js" > "/tmp/${scraper}_output.log" 2>&1; then
    END=$(date +%s)
    DURATION=$((END - START))
    echo "    ✅ PASSED ($DURATION seconds)"
    PASSED+=("$scraper")
  else
    END=$(date +%s)
    DURATION=$((END - START))
    echo "    ❌ FAILED ($DURATION seconds)"
    FAILED+=("$scraper")
    # Show last few lines of error
    echo "    Error preview:"
    tail -5 "/tmp/${scraper}_output.log" | sed 's/^/    /'
  fi
  echo ""
done

echo "=============================================="
echo "SUMMARY"
echo "=============================================="
echo "Passed: ${#PASSED[@]} / ${#SCRAPERS[@]}"
echo "Failed: ${#FAILED[@]} / ${#SCRAPERS[@]}"
echo ""

if [ ${#PASSED[@]} -gt 0 ]; then
  echo "✅ Passed scrapers:"
  for s in "${PASSED[@]}"; do
    echo "   - $s"
  done
fi

if [ ${#FAILED[@]} -gt 0 ]; then
  echo ""
  echo "❌ Failed scrapers (need self-healing):"
  for s in "${FAILED[@]}"; do
    echo "   - $s"
  done
fi

# Save failed list for next step
echo "${FAILED[@]}" > /tmp/failed_scrapers.txt
