from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.events import AllSlotsReset
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
import requests
from datetime import datetime

# API Base URL
API_BASE_URL = "http://localhost:5000/api"


def parse_backend_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    value_text = str(value).strip()
    parsed_formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d',
    ]

    for date_format in parsed_formats:
        try:
            return datetime.strptime(value_text, date_format)
        except ValueError:
            continue

    iso_text = value_text.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(iso_text)
    except ValueError:
        return None


def format_backend_datetime(value, output_format):
    parsed = parse_backend_datetime(value)
    if parsed:
        return parsed.strftime(output_format)
    return str(value) if value is not None else 'N/A'


def normalize_severity(value: str) -> str:
    if not value:
        return ''

    value_map = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High',
        'critical': 'High',
        'urgent': 'High',
        'major': 'High',
    }
    return value_map.get(value.strip().lower(), value.strip())


def first_text_value(tracker: Tracker, *slot_names: str) -> str:
    for slot_name in slot_names:
        value = (tracker.get_slot(slot_name) or '').strip()
        if value:
            return value
    return ''


def get_response_payload(response):
    try:
        return response.json()
    except Exception:
        return {}


def classify_login_help(message: str) -> tuple[str, str]:
    text = (message or '').strip().lower()

    guidance = [
        (
            'Forgot Password',
            ('forgot my password', 'reset my password', 'password reset', 'password reset help', 'password reset needed'),
            'Please reset your password using the reset link or the password recovery flow.',
        ),
        (
            'Invalid Password',
            ('wrong password', 'password incorrect', 'invalid password', 'password is wrong'),
            'The password looks incorrect. Please try again or use the password reset option.',
        ),
        (
            'Cannot Login',
            ('cannot login', 'cannot log in', 'unable to sign in', 'login failed', 'sign in problem'),
            'Please verify your credentials and try again. If the issue continues, reset your password.',
        ),
        (
            'Account Locked',
            ('account locked', 'locked account', 'too many failed attempts'),
            'Your account appears locked after repeated failed attempts. Please contact support or wait for the lockout period to end.',
        ),
        (
            'Authentication Failed',
            ('authentication failed', 'auth failed', 'auth error'),
            'Authentication failed. Please try again after a short wait and confirm your credentials are correct.',
        ),
        (
            'Email Not Registered',
            ('email not found', 'email is not found', 'email not registered', 'email not recognized', 'my email is not found'),
            'The email address is not registered. Please check the email or contact support to confirm the account details.',
        ),
        (
            'UID Problem',
            ('uid is not working', 'invalid uid', 'wrong uid', 'employee id is not working', 'customer id is not working'),
            'Please verify your UID or customer ID and try again. If it still fails, contact support to confirm the record.',
        ),
        (
            'OTP Issue',
            ('otp not received', 'otp failed', 'otp issue', 'otp not working'),
            'The OTP was not received. Please check your network, resend the code, or confirm the registered contact details.',
        ),
        (
            'Session Expired',
            ('session expired', 'login timeout', 'session timed out'),
            'Your session expired. Please sign in again to continue.',
        ),
        (
            'Browser Issue',
            ('login page not loading', 'browser issue', 'cache issue', 'clear cache', 'page not loading'),
            'This looks like a browser or cache issue. Please refresh the page, clear the browser cache, or try another browser.',
        ),
        (
            'Server Issue',
            ('login server down', 'authentication server down', 'server issue', 'backend authentication issue'),
            'The authentication server appears to be unavailable. Please try again later or contact the support team.',
        ),
        (
            'MFA/2FA Problem',
            ('2fa code failed', 'mfa problem', 'two-factor issue', 'mfa/2fa', 'mfa failed', '2fa failed'),
            'The MFA or 2FA step failed. Please verify your authenticator or request a new verification code.',
        ),
        (
            'Permission Denied',
            ('access denied', 'permission denied', 'role restriction'),
            'Access is denied for this account. Please contact your administrator to review your permissions.',
        ),
        (
            'Dashboard Not Opening',
            ('dashboard not opening', 'dashboard not loading', 'login success but dashboard fails'),
            'Login may be successful, but the dashboard is not loading. Please refresh the page or clear the browser cache.',
        ),
    ]

    for label, keywords, response in guidance:
        if any(keyword in text for keyword in keywords):
            return label, response

    return (
        'Login Help',
        'For login help, try resetting your password, confirm your username, and make sure the account is active.',
    )

class ActionGetIssueStatus(Action):
    def name(self) -> Text:
        return "action_get_issue_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        issue_id = tracker.get_slot("issue_id")
        
        if not issue_id:
            dispatcher.utter_message(text="I need an Issue ID to check the status. Please provide one.")
            return []
        
        try:
            # Call the API to get issue details
            response = requests.get(f"{API_BASE_URL}/incidents/{issue_id}")
            
            if response.status_code == 200:
                issue = response.json()
                
                # Format the response
                logged_date = format_backend_datetime(issue.get('start_date') or issue.get('logged_date'), '%Y-%m-%d %H:%M')
                
                message = f"📋 Issue: {issue['issue_id']}\n"
                message += f"📝 Summary: {issue.get('summary', 'N/A')}\n"
                message += f"🔴 Status: {issue.get('status', 'N/A')}\n"
                message += f"⚠️ Severity: {issue.get('severity', 'N/A')}\n"
                message += f"📅 Logged on: {logged_date}\n"
                
                if issue.get('assigned_to'):
                    message += f"👤 Assigned to: {issue.get('assigned_to')}\n"
                    
                    if issue.get('agent'):
                        message += f"👤 Agent: {issue['agent'].get('name', 'N/A')}\n"
                        if issue['agent'].get('email'):
                            message += f"📧 Agent email: {issue['agent'].get('email')}\n"
                
                if issue.get('progress_notes'):
                    message += f"\n📝 Progress Notes:\n{issue.get('progress_notes')}\n"
                
                if issue.get('resolution_description') and issue.get('status') in ['Resolved', 'Closed']:
                    message += f"\n✅ Resolution:\n{issue.get('resolution_description')}\n"
                
                dispatcher.utter_message(text=message)
            else:
                error_message = None
                try:
                    error_message = response.json().get('message')
                except Exception:
                    error_message = response.text.strip() if response.text else None
                dispatcher.utter_message(text=error_message or f"Issue {issue_id} not found or there was an error retrieving the information.")
        
        except Exception as e:
            dispatcher.utter_message(text=f"Error retrieving issue details: {str(e)}")
        
        return []

class ActionGetAgentIssues(Action):
    def name(self) -> Text:
        return "action_get_agent_issues"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        agent_id = tracker.get_slot("agent_id")
        
        if not agent_id:
            dispatcher.utter_message(text="I need an Agent ID to check their issues. Please provide one.")
            return []
        
        try:
            # First check if agent exists
            agent_response = requests.get(f"{API_BASE_URL}/agents/{agent_id}")
            
            if agent_response.status_code != 200:
                dispatcher.utter_message(text=f"Agent {agent_id} not found.")
                return []
            
            agent = agent_response.json()
            
            # Get agent's issues
            response = requests.get(f"{API_BASE_URL}/agents/{agent_id}/incidents")
            
            if response.status_code == 200:
                issues = response.json()
                
                if not issues:
                    dispatcher.utter_message(text=f"Agent {agent['name']} ({agent_id}) has no issues assigned.")
                    return []
                
                message = f"📋 Issues assigned to {agent['name']} ({agent_id}):\n\n"
                
                for idx, issue in enumerate(issues, 1):
                    status_emoji = "🔴" if issue['status'] in ['New', 'Assigned'] else "🟡" if issue['status'] == 'In Progress' else "🟢"
                    message += f"{idx}. {status_emoji} {issue['issue_id']} - {issue['summary']} ({issue['status']})\n"
                
                message += f"\nTotal: {len(issues)} issues"
                
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text=f"Error retrieving issues for agent {agent_id}.")
        
        except Exception as e:
            dispatcher.utter_message(text=f"Error retrieving agent issues: {str(e)}")
        
        return []

class ActionGetTotalIssues(Action):
    def name(self) -> Text:
        return "action_get_total_issues"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            # Get analytics stats
            response = requests.get(f"{API_BASE_URL}/analytics/stats")
            
            if response.status_code == 200:
                stats = response.json()

                total_issues = stats.get('total_issues', stats.get('total_incidents', 'N/A'))
                open_issues = stats.get('open_issues', stats.get('open_incidents', 'N/A'))
                resolved_today = stats.get('resolved_today', 'N/A')
                high_severity = stats.get('high_severity', stats.get('high_severity_incidents', 'N/A'))
                avg_resolution = stats.get('avg_resolution_time', f"{stats.get('avg_resolution_hours', 'N/A')} hours")
                
                message = f"📊 Support System Statistics:\n\n"
                message += f"📝 Total Issues: {total_issues}\n"
                message += f"🔴 Open Issues: {open_issues}\n"
                message += f"✅ Resolved Today: {resolved_today}\n"
                message += f"⚠️ High Severity Issues: {high_severity}\n"
                message += f"⏱️ Average Resolution Time: {avg_resolution}\n"
                
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text="Error retrieving issue statistics.")
        
        except Exception as e:
            dispatcher.utter_message(text=f"Error retrieving total issues: {str(e)}")
        
        return []


class ActionAssignAgent(Action):
    def name(self) -> Text:
        return "action_assign_agent"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        issue_id = first_text_value(tracker, 'issue_id')
        if not issue_id:
            dispatcher.utter_message(text="Please provide the issue ID you want to assign.")
            return []

        try:
            incident_response = requests.get(f"{API_BASE_URL}/incidents/{issue_id}", timeout=15)
            if incident_response.status_code != 200:
                dispatcher.utter_message(text=f"Incident {issue_id} not found.")
                return []

            agents_response = requests.get(f"{API_BASE_URL}/agents", timeout=15)
            if agents_response.status_code != 200:
                dispatcher.utter_message(text="I could not load available agents right now.")
                return []

            agents = agents_response.json() or []
            if not agents:
                dispatcher.utter_message(text="No agents are available to assign right now.")
                return []

            chosen_agent = sorted(agents, key=lambda item: (item.get('open_issue_count', 0), item.get('name', ''), item.get('uid', '')))[0]
            assign_payload = {
                'issue_id': issue_id,
                'agent_uid': chosen_agent.get('uid'),
            }
            assign_response = requests.put(f"{API_BASE_URL}/incidents/assign", json=assign_payload, timeout=15)
            if assign_response.status_code not in (200, 201):
                error_payload = get_response_payload(assign_response)
                dispatcher.utter_message(text=error_payload.get('message') or f"Failed to assign {issue_id}.")
                return []

            dispatcher.utter_message(
                text=f"Agent {chosen_agent.get('name', chosen_agent.get('uid', 'N/A'))} assigned successfully to issue {issue_id}."
            )
        except Exception as e:
            dispatcher.utter_message(text=f"Error assigning agent: {str(e)}")

        return []


class ActionLoginIssue(Action):
    def name(self) -> Text:
        return "action_login_issue"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        latest_message = tracker.latest_message.get('text') if tracker.latest_message else ''
        label, response_text = classify_login_help(latest_message)
        dispatcher.utter_message(text=f"{label}: {response_text}")
        return []


class ActionNetworkIssue(Action):
    def name(self) -> Text:
        return "action_network_issue"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="Please restart your router.")
        return []


class ActionPaymentIssue(Action):
    def name(self) -> Text:
        return "action_payment_issue"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="Your payment is pending verification.")
        return []


class ActionEscalateIssue(Action):
    def name(self) -> Text:
        return "action_escalate_issue"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        issue_id = first_text_value(tracker, 'issue_id')
        if not issue_id:
            dispatcher.utter_message(text="Please provide the issue ID you want to escalate.")
            return []

        try:
            response = requests.put(
                f"{API_BASE_URL}/incidents/{issue_id}/severity",
                json={'severity': 'High', 'progress_notes': 'Escalated to high priority from chatbot'},
                timeout=15,
            )
            if response.status_code not in (200, 201):
                error_payload = get_response_payload(response)
                dispatcher.utter_message(text=error_payload.get('message') or f"Failed to escalate issue {issue_id}.")
                return []

            dispatcher.utter_message(text="Issue escalated to high priority.")
        except Exception as e:
            dispatcher.utter_message(text=f"Error escalating issue: {str(e)}")

        return []


class ActionResolveIssue(Action):
    def name(self) -> Text:
        return "action_resolve_issue"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        issue_id = first_text_value(tracker, 'issue_id')
        agent_id = first_text_value(tracker, 'agent_id')

        if not issue_id:
            dispatcher.utter_message(text="Please provide the issue ID you want to resolve.")
            return []

        if not agent_id:
            dispatcher.utter_message(text="Please provide the agent ID assigned to this issue.")
            return []

        try:
            response = requests.put(
                f"{API_BASE_URL}/incidents/{issue_id}/status",
                json={
                    'status': 'Resolved',
                    'agent_uid': agent_id,
                    'progress_notes': 'Marked as resolved from chatbot',
                },
                timeout=15,
            )
            if response.status_code not in (200, 201):
                error_payload = get_response_payload(response)
                dispatcher.utter_message(text=error_payload.get('message') or f"Failed to resolve issue {issue_id}.")
                return []

            dispatcher.utter_message(text="Ticket marked as resolved.")
        except Exception as e:
            dispatcher.utter_message(text=f"Error resolving issue: {str(e)}")

        return []

class ActionGetIssuesByStatus(Action):
    def name(self) -> Text:
        return "action_get_issues_by_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        status = tracker.get_slot("status")
        
        if not status:
            dispatcher.utter_message(text="I need a status to filter issues. Please provide one (New, Assigned, In Progress, Resolved, Closed).")
            return []
        
        try:
            # Search for issues with the given status
            response = requests.get(f"{API_BASE_URL}/incidents/search?status={status}")
            
            if response.status_code == 200:
                issues = response.json()
                
                if not issues:
                    dispatcher.utter_message(text=f"No issues found with status '{status}'.")
                    return []
                
                message = f"📋 Issues with status '{status}':\n\n"
                
                for idx, issue in enumerate(issues[:10], 1):  # Limit to 10 issues
                    message += f"{idx}. {issue['issue_id']} - {issue['summary']} (Severity: {issue['severity']})\n"
                
                if len(issues) > 10:
                    message += f"\n...and {len(issues) - 10} more."
                
                message += f"\nTotal: {len(issues)} issues with status '{status}'"
                
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text=f"Error retrieving issues with status '{status}'.")
        
        except Exception as e:
            dispatcher.utter_message(text=f"Error retrieving issues by status: {str(e)}")
        
        return []

class ActionGetIssuesBySeverity(Action):
    def name(self) -> Text:
        return "action_get_issues_by_severity"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        severity = tracker.get_slot("severity")
        
        if not severity:
            dispatcher.utter_message(text="I need a severity level to filter issues. Please provide one (Low, Medium, High).")
            return []
        
        try:
            # Search for issues with the given severity
            response = requests.get(f"{API_BASE_URL}/incidents/search?severity={severity}")
            
            if response.status_code == 200:
                issues = response.json()
                
                if not issues:
                    dispatcher.utter_message(text=f"No issues found with severity '{severity}'.")
                    return []
                
                message = f"📋 Issues with severity '{severity}':\n\n"
                
                for idx, issue in enumerate(issues[:10], 1):  # Limit to 10 issues
                    status_emoji = "🔴" if issue['status'] in ['New', 'Assigned'] else "🟡" if issue['status'] == 'In Progress' else "🟢"
                    message += f"{idx}. {status_emoji} {issue['issue_id']} - {issue['summary']} ({issue['status']})\n"
                
                if len(issues) > 10:
                    message += f"\n...and {len(issues) - 10} more."
                
                message += f"\nTotal: {len(issues)} issues with severity '{severity}'"
                
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text=f"Error retrieving issues with severity '{severity}'.")
        
        except Exception as e:
            dispatcher.utter_message(text=f"Error retrieving issues by severity: {str(e)}")
        
        return []

class ActionGetIssuesByDateRange(Action):
    def name(self) -> Text:
        return "action_get_issues_by_date_range"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        start_date = tracker.get_slot("start_date")
        end_date = tracker.get_slot("end_date")
        
        if not start_date:
            dispatcher.utter_message(text="I need a start date to filter issues. Please provide one (YYYY-MM-DD).")
            return []
        
        if not end_date:
            dispatcher.utter_message(text="I need an end date to filter issues. Please provide one (YYYY-MM-DD).")
            return []
        
        try:
            # Validate dates
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                dispatcher.utter_message(text="Invalid date format. Please use YYYY-MM-DD.")
                return []
            
            # Search for issues in the given date range
            response = requests.get(f"{API_BASE_URL}/incidents/search?date_from={start_date}&date_to={end_date}")
            
            if response.status_code == 200:
                issues = response.json()
                
                if not issues:
                    dispatcher.utter_message(text=f"No issues found between {start_date} and {end_date}.")
                    return []
                
                message = f"📋 Issues between {start_date} and {end_date}:\n\n"
                
                for idx, issue in enumerate(issues[:10], 1):  # Limit to 10 issues
                    logged_date = format_backend_datetime(issue.get('start_date') or issue.get('logged_date'), '%Y-%m-%d')
                    message += f"{idx}. {issue['issue_id']} - {issue['summary']} ({issue['status']}, {logged_date})\n"
                
                if len(issues) > 10:
                    message += f"\n...and {len(issues) - 10} more."
                
                message += f"\nTotal: {len(issues)} issues between {start_date} and {end_date}"
                
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text=f"Error retrieving issues between {start_date} and {end_date}.")
        
        except Exception as e:
            dispatcher.utter_message(text=f"Error retrieving issues by date range: {str(e)}")
        
        return []


class ActionCreateIncident(Action):
    def name(self) -> Text:
        return "action_create_incident"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        customer_id = (tracker.get_slot("customer_id") or "").strip()
        customer_email = (tracker.get_slot("customer_email") or "").strip()
        summary = (tracker.get_slot("summary") or "").strip()
        severity = normalize_severity(tracker.get_slot("severity") or "")

        if not customer_id or not customer_email or not summary or not severity:
            dispatcher.utter_message(text="I still need the customer ID, email, issue summary, and severity to create the incident.")
            return []

        if severity not in ['Low', 'Medium', 'High']:
            dispatcher.utter_message(text="Severity must be Low, Medium, or High.")
            return []

        payload = {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "summary": summary,
            "description": summary,
            "severity": severity,
        }

        try:
            response = requests.post(f"{API_BASE_URL}/incidents", json=payload, timeout=15)
            try:
                data = response.json()
            except Exception:
                data = {}

            if response.status_code not in (200, 201):
                dispatcher.utter_message(text=data.get('message') or data.get('error') or 'Failed to create incident.')
                return []

            issue_id = data.get('issue_id') or 'N/A'
            email_sent = data.get('email_sent') is True
            if email_sent:
                dispatcher.utter_message(text=f"Incident created successfully. Issue ID {issue_id} has been sent to {customer_email}.")
            else:
                error_text = data.get('error')
                suffix = f" Reason: {error_text}" if error_text else ''
                dispatcher.utter_message(text=f"Incident created, but the issue ID email was not confirmed. Issue ID: {issue_id}.{suffix}")

            return [AllSlotsReset()]
        except Exception as e:
            dispatcher.utter_message(text=f"Error creating incident: {str(e)}")
            return []


class ValidateIncidentCreationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_incident_creation_form"

    def validate_customer_id(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate customer_id value."""
        customer_id = (slot_value or "").strip()
        if not customer_id:
            dispatcher.utter_message(text="Your Customer ID doesn't Exist")
            return {"customer_id": None}

        try:
            response = requests.get(f"{API_BASE_URL}/customers/{customer_id}", timeout=15)
            if response.status_code == 200:
                return {"customer_id": customer_id}
            else:
                dispatcher.utter_message(text="Your Customer ID doesn't Exist")
                return {"customer_id": None}
        except Exception:
            dispatcher.utter_message(text="Your Customer ID doesn't Exist")
            return {"customer_id": None}
