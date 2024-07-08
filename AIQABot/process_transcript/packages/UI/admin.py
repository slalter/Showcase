from ..categorization import getGlobalCategories, getGlobalFlags, getGlobalQuestions
from packages.models.campaign import getCampaignByName, getCampaigns
from packages.models.logs import BatchReport, getFailedTranscriptProcessesByDate
from datetime import datetime, timedelta
import json

def baseHTML(start_time=None, end_time=None, campaign_name = None):
    if not campaign_name: 
        campaign = getCampaignByName('ACA')
    else:
        campaign = getCampaignByName(campaign_name)
    categories = campaign.categories

    flags =  campaign.flags
    questions =  campaign.questions
    #total_report = getReport(start_time, end_time)
    #report = getReport(start_time, end_time, campaign) #returns a report with number of calls processed, number of calls in each period for a specified timeframe. Show 1 week by default.
    campaigns = [camp for camp in getCampaigns()]

    # Read the HTML file content
    with open('packages/UI/main.html', 'r') as file:
        html_content = file.read()

    categories_html = ''
    for category in categories:
        # Add the main category with its remove and toggle visibility button
        categories_html += f'''<div class="category-group">
                                <div class="input-group">
                                <input type="text" value="{category.name}" contenteditable="true">
                                <div class="remove-btn" onclick="removeElement(this, 2)">X</div>
                                <button onclick="toggleSubcategoryVisibility(this, 'subcategories-{category.name}')">Show Subcategories</button>
                                </div>
                                '''
        
        # Add a container for subcategories, initially hidden
        categories_html += f'<div id="subcategories-{category.name}" class="subcategories" style="margin-left: 20px; display: none;">'
        
        # Iterate over subcategories if any
        for subcategory in category.subcategories:
            categories_html += f'<div class="input-group"><input type="text" value="{subcategory}" contenteditable="true"><div class="remove-btn" onclick="removeElement(this, 1)">X</div></div>'
        
            # Input group for adding a new subcategory
        categories_html += f'''<div class="input-group">
                <button onclick="addSubcategory('subcategories-{category.name}')">Add subcategory</button>
        </div></div>'''  # Note: Adjusted the addSubcategory function call to pass parameters

        # Close the subcategories and category-group div
        categories_html += '</div>'

    html_content += '</div>'
        
    flags_html = '\n'.join(f'<div class="input-group"><input type="text" value="{flag}" contenteditable="true"><div class="remove-btn" onclick="this.parentElement.remove()">X</div></div>' for flag in flags)
  
    questions_html = '\n'.join(f'<div class="input-group"><input type="text" value="{question}" contenteditable="true"><div class="remove-btn" onclick="this.parentElement.remove()">X</div></div>' for question in questions)
 
    html_content = html_content.replace('<!-- Categories will be dynamically added here -->', categories_html)
    html_content = html_content.replace('<!-- Flags will be dynamically added here -->', flags_html)
    html_content = html_content.replace('<!-- Questions will be dynamically added here -->', questions_html)

    # Update campaigns dropdown
    campaign_options_html = ' '.join([f'\"{campaign.name}\",' for campaign in campaigns])
    campaign_dropdown_placeholder = '<!-- camp options here-->'
    html_content = html_content.replace(campaign_dropdown_placeholder, campaign_options_html, 1)
    # Update active camp
    active_camp = f"\"{campaign_name}\""
    active_camp_placeholder = 'ACTIVE_CAMP_REPLACE'
    html_content = html_content.replace(active_camp_placeholder, active_camp, 1)
    # Update report section with calls by category data

    report_section_placeholder = '<!-- Display report summary here -->'

    report_html = '<h4>Failed Calls</h4>'
    for i in range(3):
        date = datetime.utcnow().date() - timedelta(days=i)
        m, d, y = date.month, date.day, date.year
        failed_transcripts = getFailedTranscriptProcessesByDate(m, d, y)

        # If there are failed transcripts for the day, add them to the HTML
        if failed_transcripts:
            report_html += f"<div><button onclick='this.nextElementSibling.style.display = \"block\";'>{date.strftime('%m/%d/%Y')}: {len(failed_transcripts)} failures.</button><div style='display:none;'>"


            for call_id, attempts in failed_transcripts.items():
                report_html += f"<p>uuid:{call_id}<br>"
                for attempt in attempts:
                    report_html += f"attempt:<pre>{json.dumps(attempt, indent=4)}</pre></p>"


            report_html += "</div></div>"

    report_html += "</div>"
    report_html += '<h4>Batch Reports</h4>'
  
    for br in BatchReport.getAll():
        report_html+= f'<p>Batch Report: <span>{br}</span></p>'
    
    html_content = html_content.replace(report_section_placeholder, report_html, 1)

    return html_content
