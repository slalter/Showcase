from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models.utils.smart_uuid import SmartUUID
import uuid
import traceback
import json
from datetime import timedelta


class ConversationLog(Base):
    __tablename__ = 'conversation_log'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    dbconversation_id = Column(SmartUUID(), ForeignKey('db_conversation.id'), nullable=False, index=True)
    type = Column(String(10000), nullable = False, default = 'NO TYPE')
    content = Column(JSON, nullable = False, default = {})
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self):
        out = self.content
        out.update({
            'type':self.type,
            'created_at': self.created_at.isoformat() if self.created_at else None
            }
        )
        return out
    

def formatReportToHTML(report_data):
    # Predefined colors
    colors = ["lightblue", "lightgreen", "lightcoral", "lightpink", "lightseagreen", "lightsalmon", "lightsteelblue", "lightyellow", "lightcyan"]
    color_map = {}  # Map to assign colors to types

    # Combine and sort all items
    all_items = []
    for message in report_data['messages']:
        all_items.append({
            'type': 'message',
            'timestamp': datetime.strptime(message['created_at'], '%Y-%m-%d %H:%M:%S.%f'),
            'content': message['content'],
            'role': message['role']
        })

    for log in report_data['logs']:
        try:
            all_items.append({
                'type': log['type'],
                'timestamp': datetime.strptime(log['created_at'], '%Y-%m-%dT%H:%M:%S.%f'),
                'content': {key:value for key, value in log.items() if key not in ['type','created_at']}
            })
        except Exception as e:
            #add data about the item that failed to the exception, raise
            e.args += (f"failed to parse log: {log}",)
            raise e
        
            

    total_cost = 0
    for call in report_data['LLMCalls']:
        total_cost += call['total_cost']
        all_items.append({
            'type': f'LLMCall: {call["request_type"]}',
            'timestamp': call['created_at'],
            'content': {key:value for key, value in call.items() if key not in ['type','created_at']}
        })

    #make a report on where time was spent by type, across ALL things.
    time_by_type = {}
    previtem = None
    sorted_items = sorted(all_items, key=lambda x: x['timestamp'])
    for item in sorted_items:
        if previtem:
            time_by_type[previtem['type'].split(':')[0]] = round((time_by_type.get(previtem['type'], 0) + (item['timestamp'] - previtem['timestamp']).total_seconds()), 2)
        previtem = item
    
    #sort by highest time usage
    time_by_type = {k: v for k, v in sorted(time_by_type.items(), key=lambda item: item[1], reverse=True)}

    all_items.append({
        'type': 'TimeSpentByType',
        'timestamp': datetime(2000,1,1),
        'content': time_by_type
    })

    #track the total cost of each call['request_type'], sort them by most expensive, and display them in the report.
    cost_by_type = {}
    for call in report_data['LLMCalls']:
        cost_by_type[call['request_type'].split(':')[0]] = round(cost_by_type.get(call['request_type'], 0) + call['total_cost'], 2)
    #sort by highest cost
    cost_by_type = {k: v for k, v in sorted(cost_by_type.items(), key=lambda item: item[1], reverse=True)}
    #make the timestamp long ago
    all_items.append({
        'type': 'LLMCosts',
        'timestamp': datetime(2000,1,1),
        'content': cost_by_type
    })

    

    if not all_items:
        return "no items on this report yet!"
    try:
        all_items.sort(key=lambda x: x['timestamp'])
        if len(all_items) >3:
            total_time = all_items[-1]['timestamp'] - all_items[2]['timestamp']
            rounded_total_time_seconds = round(total_time.total_seconds())
            rounded_total_time = timedelta(seconds=rounded_total_time_seconds)
        else:
            rounded_total_time = timedelta(seconds=0)
    except Exception as e:
        print(f"failed to calculate total time: {e}")
        rounded_total_time = timedelta(seconds=0)

    # Start HTML formatting
    html = "<html><head><title>Conversation Report</title></head><body>"
    html += "<div style='display: flex; flex-direction: column; align-items: center;'>"
    html += f"<div style='width: 100%; text-align: center; margin: 20px 0; padding: 10px; background-color: #f0f0f0; border-radius: 8px;'>"
    html += f"<h2>Total Cost: ${total_cost:.2f}<span style='margin-left: 80px;'>Total time elapsed: {rounded_total_time} </h2>"
    html += "</div>"

    for item in all_items:
        # Assign a new color to each new type
        if item['type'] not in color_map:
            color_map[item['type']] = colors[len(color_map) % len(colors)]

        # Formatting for Messages
        if item['type'] == 'message':
            align = 'left' if item['role'] == 'assistant' else 'right'
            html += f"<div style='text-align: {align}; width: 80%; background-color: lightgray; margin: 5px; padding: 5px;'>"
            html += f"<p><b>{item['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}</b>: <p><pre style='white-space: pre-wrap;'>{item['content']}</pre></p>"
            html += "</div>"
        # Formatting for Logs
        else:
            color = color_map[item['type']]
            html += f"<div style='text-align: center; width: 80%; background-color: {color}; margin: 5px; padding: 5px;'>"
            html += f"<details><summary>{item['type'].capitalize()} {item['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}</summary>"
            if isinstance(item['content'], dict):
                content = item['content']
            else:
                try:
                    content = json.loads(item['content'])
                except Exception as e:
                    content = str(item['content']) + "\n unable to parse!"
                    html += f"<p><pre style='white-space: pre-wrap; text-align: left;'>{content}</pre><p>"
                    html += "</details></div>"
                    return html
            for key, value in content.items():
                text = key + ":" + str(value).replace('\\\\n','<br>').replace('\\n','<br>').replace('\n','<br>')
                html += f'<p style="text-align: left; white-space: pre-wrap;">{text}</p>'

            html += "</details></div>"

    html += "</div></body></html>"
    return html