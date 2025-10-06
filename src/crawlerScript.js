// ==UserScript==
// @name         Otosor Car Listings Scraper (Single Page, Auto-Click Teşekkürler, Updated Selectors)
// @namespace    http://tampermonkey.net/
// @version      1.7
// @description  Scrapes car listings from a single page on otosor.com.tr, auto-clicks "Teşekkürler" button, logs actions, and downloads as CSV
// @author       Grok
// @match        https://www.otosor.com.tr/araclar*
// @grant        none
// ==/UserScript==
(async function() {
    'use strict';
    // Log array to store messages
    const logs = [];
    const log = (message) => {
        const timestamp = new Date().toISOString();
        logs.push(`[${timestamp}] ${message}`);
        console.log(`[${timestamp}] ${message}`);
    };
    // Function to download logs as a file
    function downloadLogs() {
        const logContent = logs.join('\n');
        const blob = new Blob([logContent], { type: 'text/plain;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', 'data/otosor_scraper.log');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        log('Log file downloaded: data/otosor_scraper.log');
    }
    // Utility function to wait for elements with a more robust check
    function waitForElements(selector, timeout = 30000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const check = () => {
                const elements = document.querySelectorAll(selector);
                // Check for a minimum number of elements to ensure the page has loaded
                if (elements.length > 5) {
                    resolve(elements);
                } else if (Date.now() - startTime > timeout) {
                    reject(new Error(`Timeout waiting for elements: ${selector}`));
                } else {
                    setTimeout(check, 500); // Wait a bit longer to allow for loading
                }
            };
            check();
        });
    }
    // Utility function to delay execution
    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    // Function to clean text
    function cleanText(text) {
        return text ? text.replace(/\s+/g, ' ').trim() : 'N/A';
    }
    // Function to convert data to CSV and trigger download
    function downloadCSV(data, filename = 'data/otosor.csv') {
        if (!data || data.length === 0) {
            log('No data to save to CSV.');
            return;
        }
        // Step 1: Gather ALL unique column headers from the ENTIRE dataset
        const allColumnsSet = new Set();
        data.forEach(row => {
            Object.keys(row).forEach(key => allColumnsSet.add(key));
        });
        let columns = Array.from(allColumnsSet);
        // Step 2: Ensure preferred columns are at the beginning of the list
        const preferredColumns = ['İlan Linki', 'Fiyat'];
        const otherColumns = columns.filter(col => !preferredColumns.includes(col));
        const finalColumns = [...preferredColumns, ...otherColumns].filter(Boolean);
        // Step 3: Create CSV content, starting with the header row
        const csvHeader = finalColumns.join(',');
        // Step 4: Map each data row to a CSV row, ensuring all columns are included
        const csvRows = data.map(row => {
            return finalColumns.map(col => {
                const value = row[col] || 'N/A';
                return `"${String(value).replace(/"/g, '""')}"`;
            }).join(',');
        });
        // Step 5: Combine header and rows
        const csvContent = [csvHeader, ...csvRows].join('\n');
        // Create a blob and trigger download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        log(`CSV downloaded: ${filename} with ${data.length} records`);
    }
    // Function to fetch and parse a detail page
    async function fetchDetailPage(url, index) {
        log(`Fetching detail page ${index + 1}: ${url}`);
        try {
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://www.otosor.com.tr/araclar?sorting=price-lowest'
                }
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const text = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(text, 'text/html');
            const data = { 'İlan Linki': url };
            // Extract price
            const priceElem = doc.querySelector('p.text-18.font-bold.leading-7');
            if (priceElem) {
                const priceText = cleanText(priceElem.textContent);
                const priceDigits = priceText.replace(/[^\d]/g, '');
                data['Fiyat'] = priceDigits || 'N/A';
                log(`Price found: ${data['Fiyat']}`);
            } else {
                log(`Price element not found for URL: ${url}`);
                data['Fiyat'] = 'N/A';
            }
            // Extract properties
            const propsContainer = doc.querySelector('.scrollbar-hide.flex.h-full.flex-col.justify-center.gap-0.overflow-hidden.pt-4.md\\:flex-row.md\\:gap-8');
            if (propsContainer) {
                const keys = propsContainer.querySelectorAll('li > div:first-child.text-16.leading-6.text-black-primary');
                const values = propsContainer.querySelectorAll('li > div:last-child.text-16.font-medium.leading-6.text-black-primary');
                log(`Found ${keys.length} keys and ${values.length} values for URL: ${url}`);
                if (keys.length !== values.length) {
                    log(`Mismatch between keys (${keys.length}) and values (${values.length}) for URL: ${url}`);
                }
                keys.forEach((key, idx) => {
                    const keyText = cleanText(key.textContent);
                    const valueText = values[idx] ? cleanText(values[idx].textContent) : 'N/A';
                    data[keyText] = valueText;
                });
            } else {
                log(`Properties container not found for URL: ${url}`);
            }
            return data;
        } catch (error) {
            log(`Error fetching detail page ${url}: ${error.message}`);
            return { 'İlan Linki': url, 'Fiyat': 'N/A' };
        }
    }
    // Main scraping function for a single page
    async function scrapeSinglePage() {
        const allData = [];
        const processedUrls = new Set();
        try {
            // Click the "Teşekkürler" button
            log('Checking for "Teşekkürler" button...');
            const thanksBtn = Array.from(document.querySelectorAll('button'))
                .find(btn => btn.className.includes('button-primary') && btn.textContent.includes('Teşekkürler'));
            if (thanksBtn) {
                log('Clicking "Teşekkürler" button...');
                thanksBtn.click();
                await delay(2000); // Longer delay to allow page to settle
            } else {
                log('No "Teşekkürler" button found. Continuing without clicking.');
            }
            log('Waiting for listings to load...');
            const listingElements = await waitForElements('.flex.w-full.items-center.justify-between.gap-1', 60000); // Increased timeout
            log(`Found ${listingElements.length} listing elements`);
            const listingUrls = [];
            listingElements.forEach((elem, index) => {
                const link = elem.querySelector('a');
                if (link && link.href) {
                    const fullUrl = link.href.startsWith('http') ? link.href : `https://www.otosor.com.tr${link.href}`;
                    if (!processedUrls.has(fullUrl)) {
                        listingUrls.push({ url: fullUrl, index });
                        processedUrls.add(fullUrl);
                        log(`Listing URL ${index + 1}: ${fullUrl}`);
                    } else {
                        log(`Skipping duplicate URL: ${fullUrl}`);
                    }
                } else {
                    log(`No <a> tag found in listing element ${index + 1}`);
                }
            });
            if (listingUrls.length === 0) {
                log('No valid listing URLs found on the page.');
                downloadLogs();
                return;
            }
            log(`Processing ${listingUrls.length} unique listings`);
            // Fetch detail pages sequentially
            for (const { url, index } of listingUrls) {
                const data = await fetchDetailPage(url, index);
                if (data && Object.keys(data).length > 1) { // Ensure data has more than just the URL
                    allData.push(data);
                } else {
                    log(`No useful data retrieved from ${url}`);
                }
                await delay(randomInt(1000, 3000)); // Random delay between 1-3 seconds
            }
            // Save data to CSV
            if (allData.length > 0) {
                downloadCSV(allData, 'data/otosor.csv');
                log(`Data saved. Total listings scraped: ${allData.length}`);
                log(`Columns found: ${[...new Set(allData.flatMap(Object.keys))].join(', ')}`);
            } else {
                log('No data scraped. No CSV file created.');
            }
        } catch (error) {
            log(`Error during scraping: ${error.message}`);
            if (allData.length > 0) {
                downloadCSV(allData, 'data/otosor_intermediate_error.csv');
                log('Saved intermediate data due to error.');
            } else {
                log('No data to save due to error.');
            }
        } finally {
            downloadLogs();
        }
    }
    // Utility function to generate random integer between min and max
    function randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }
    // Start scraping
    log('Starting Otosor scraper for a single page...');
    await scrapeSinglePage();
})();