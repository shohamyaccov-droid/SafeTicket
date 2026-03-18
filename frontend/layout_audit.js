/**
 * Layout Audit Script - Run in Browser Console
 * 
 * Instructions:
 * 1. Open browser DevTools (F12)
 * 2. Navigate to Home page
 * 3. Paste this script in Console
 * 4. Review the audit results
 */

(function() {
  console.log('🔍 LAYOUT AUDIT - Starting...\n');
  
  const audit = {
    hero: {},
    grid: {},
    cards: {},
    images: {},
    conflicts: []
  };
  
  // 1. Hero Section Audit
  const heroSection = document.querySelector('.hero-search-section');
  if (heroSection) {
    const computed = window.getComputedStyle(heroSection);
    audit.hero = {
      height: computed.height,
      backgroundSize: computed.backgroundSize,
      aspectRatio: computed.aspectRatio,
      objectFit: computed.objectFit,
      width: computed.width
    };
    
    console.log('📐 HERO SECTION:');
    console.log('  Height:', audit.hero.height, audit.hero.height === '450px' ? '✅' : '❌');
    console.log('  Background-Size:', audit.hero.backgroundSize, audit.hero.backgroundSize.includes('cover') ? '✅' : '❌');
    console.log('  Width:', audit.hero.width);
    
    if (computed.aspectRatio && computed.aspectRatio !== 'none') {
      audit.conflicts.push('Hero has aspect-ratio that may conflict with fixed height');
    }
    if (computed.objectFit && computed.objectFit !== 'none') {
      audit.conflicts.push('Hero has object-fit (should not be on container)');
    }
  }
  
  // 2. Grid Layout Audit
  const grid = document.querySelector('.trending-events-grid');
  if (grid) {
    const computed = window.getComputedStyle(grid);
    audit.grid = {
      gridTemplateColumns: computed.gridTemplateColumns,
      gap: computed.gap,
      display: computed.display,
      width: computed.width
    };
    
    console.log('\n📊 GRID LAYOUT:');
    console.log('  Grid-Template-Columns:', audit.grid.gridTemplateColumns);
    const is4Columns = audit.grid.gridTemplateColumns.includes('repeat(4') || 
                       audit.grid.gridTemplateColumns.split(' ').length === 4;
    console.log('  4 Columns:', is4Columns ? '✅' : '❌');
    console.log('  Gap:', audit.grid.gap);
    console.log('  Display:', audit.grid.display);
    
    // Count visible cards
    const cards = grid.querySelectorAll('.trending-event-card');
    console.log('  Visible Cards:', cards.length);
    if (cards.length >= 4) {
      const first4 = Array.from(cards).slice(0, 4);
      const allInRow = first4.every(card => {
        const rect = card.getBoundingClientRect();
        return rect.top === first4[0].getBoundingClientRect().top;
      });
      console.log('  First 4 in Same Row:', allInRow ? '✅' : '❌');
    }
  }
  
  // 3. Card Audit
  const cards = document.querySelectorAll('.trending-event-card');
  if (cards.length > 0) {
    const firstCard = cards[0];
    const computed = window.getComputedStyle(firstCard);
    const rect = firstCard.getBoundingClientRect();
    
    audit.cards = {
      maxWidth: computed.maxWidth,
      width: computed.width,
      actualWidth: rect.width + 'px',
      height: computed.height,
      actualHeight: rect.height + 'px'
    };
    
    console.log('\n🃏 CARD STYLES:');
    console.log('  Max-Width:', audit.cards.maxWidth, audit.cards.maxWidth === '280px' ? '✅' : '❌');
    console.log('  Computed Width:', audit.cards.width);
    console.log('  Actual Width:', audit.cards.actualWidth);
    console.log('  Actual Height:', audit.cards.actualHeight);
    
    const actualWidthNum = parseFloat(audit.cards.actualWidth);
    if (actualWidthNum > 300) {
      audit.conflicts.push(`Card width (${actualWidthNum}px) exceeds 280px max-width`);
    }
  }
  
  // 4. Image Audit
  const images = document.querySelectorAll('.event-image');
  if (images.length > 0) {
    const firstImage = images[0];
    const computed = window.getComputedStyle(firstImage);
    const rect = firstImage.getBoundingClientRect();
    
    audit.images = {
      objectFit: computed.objectFit,
      objectPosition: computed.objectPosition,
      width: computed.width,
      height: computed.height,
      actualWidth: rect.width + 'px',
      actualHeight: rect.height + 'px',
      naturalWidth: firstImage.naturalWidth,
      naturalHeight: firstImage.naturalHeight
    };
    
    console.log('\n🖼️ IMAGE STYLES:');
    console.log('  Object-Fit:', audit.images.objectFit, audit.images.objectFit === 'cover' ? '✅' : '❌');
    console.log('  Object-Position:', audit.images.objectPosition);
    console.log('  Actual Size:', audit.images.actualWidth, 'x', audit.images.actualHeight);
    console.log('  Natural Size:', audit.images.naturalWidth, 'x', audit.images.naturalHeight);
    
    if (audit.images.objectFit !== 'cover') {
      audit.conflicts.push('Event images must use object-fit: cover');
    }
    
    // Check for stretching
    const aspectRatio = rect.width / rect.height;
    const naturalAspectRatio = firstImage.naturalWidth / firstImage.naturalHeight;
    const stretchRatio = Math.abs(aspectRatio - naturalAspectRatio) / naturalAspectRatio;
    
    if (stretchRatio > 0.1) {
      console.log('  ⚠️ WARNING: Image may be stretched (aspect ratio difference:', (stretchRatio * 100).toFixed(1) + '%)');
    } else {
      console.log('  ✅ Image aspect ratio maintained');
    }
  }
  
  // 5. Screen Width Check
  const screenWidth = window.innerWidth;
  console.log('\n📱 SCREEN INFO:');
  console.log('  Screen Width:', screenWidth + 'px');
  console.log('  Expected Cards per Row:', screenWidth >= 1920 ? '4' : screenWidth >= 768 ? '2-4' : '1-2');
  
  // 6. Summary
  console.log('\n📋 AUDIT SUMMARY:');
  console.log('  Hero Height Fixed:', audit.hero.height === '450px' ? '✅' : '❌');
  console.log('  Hero Background Cover:', audit.hero.backgroundSize?.includes('cover') ? '✅' : '❌');
  console.log('  Grid 4 Columns:', audit.grid.gridTemplateColumns?.includes('repeat(4') ? '✅' : '❌');
  console.log('  Card Max-Width 280px:', audit.cards.maxWidth === '280px' ? '✅' : '❌');
  console.log('  Images Object-Fit Cover:', audit.images.objectFit === 'cover' ? '✅' : '❌');
  
  if (audit.conflicts.length > 0) {
    console.log('\n⚠️ CONFLICTS DETECTED:');
    audit.conflicts.forEach(conflict => console.log('  -', conflict));
  } else {
    console.log('\n✅ NO CONFLICTS DETECTED');
  }
  
  // Return audit object for further inspection
  window.layoutAudit = audit;
  console.log('\n💾 Audit data saved to window.layoutAudit');
  console.log('   Inspect with: console.log(window.layoutAudit)');
  
  return audit;
})();
