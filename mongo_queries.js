// MongoDB sample query script for Incident Engine
// Run commands manually in mongosh after: use('support_system')

// Q-10 Get customer by ID
// db.customers.findOne({ customer_id: 'CUST001' });

// Q-11 Get incidents by customer email
// db.incidents.find({ customer_email: 'rahul@gmail.com' }).sort({ logged_date: -1 });

// Q-12 Incident details with agent info
// db.incidents.aggregate([
//   { $match: { issue_id: 'ISSUE001' } },
//   { $lookup: {
//       from: 'agents',
//       localField: 'assigned_to',
//       foreignField: 'uid',
//       as: 'agent'
//   } }
// ]);

// Q-13 Incidents assigned to agent
// db.incidents.find({ assigned_to: 'AGT001' }).sort({ modified_date: -1 });

// Q-14 Incident analytics counts
// db.incidents.aggregate([
//   {
//     $group: {
//       _id: null,
//       total_incidents: { $sum: 1 },
//       open_incidents: { $sum: { $cond: [{ $in: ['$status', ['Resolved', 'Closed']] }, 0, 1] } },
//       high_severity: { $sum: { $cond: [{ $eq: ['$severity', 'High'] }, 1, 0] } }
//     }
//   }
// ]);

// Q-15 Distribution by status
// db.incidents.aggregate([{ $group: { _id: '$status', total: { $sum: 1 } } }]);

// Q-16A Incident count by severity
// db.incidents.aggregate([{ $group: { _id: '$severity', total: { $sum: 1 } } }]);

// Q-16B Incident resolved count per agent
// db.agents.aggregate([
//   {
//     $lookup: {
//       from: 'incidents',
//       let: { uid: '$uid' },
//       pipeline: [
//         { $match: { $expr: { $and: [ { $eq: ['$assigned_to', '$$uid'] }, { $in: ['$status', ['Resolved', 'Closed']] } ] } } }
//       ],
//       as: 'resolved_incidents'
//     }
//   },
//   { $project: { _id: 0, name: 1, resolved_incidents: { $size: '$resolved_incidents' } } }
// ]);

// Q-17 Multi-filter search example
// db.incidents.find({
//   status: 'Assigned',
//   severity: 'High',
//   assigned_to: 'AGT001',
//   $or: [{ summary: /internet/i }, { description: /internet/i }],
//   logged_date: {
//     $gte: new Date('2026-03-01T00:00:00Z'),
//     $lte: new Date('2026-03-10T23:59:59Z')
//   }
// });
