const { MongoClient } = require('mongodb');
const cors = require('express');

// MongoDB connection URL
const mongoUrl = 'mongodb://localhost:27017'; // Change this if you're using a cloud instance
const dbName = 'userLogsDB';

// Initialize MongoDB connection
let db;

MongoClient.connect(mongoUrl)
  .then((client) => {
    console.log('Connected to MongoDB');
    db = client.db(dbName);
  })
  .catch((err) => {
    console.error('Error connecting to MongoDB', err);
  });

// This is the Netlify Function to log user actions
exports.handler = async function (event, context) {
  // Allow CORS
  const corsHandler = cors();
  return new Promise((resolve, reject) => {
    corsHandler(event, context, async () => {
      try {
        const body = JSON.parse(event.body);
        const { action, timestamp, additionalData } = body;

        console.log(`Received Action: ${action} at ${timestamp}`);

        // Insert into MongoDB
        await db.collection('DataCollections').insertOne({
          action,
          timestamp,
          additionalData,
        });

        resolve({
          statusCode: 200,
          body: JSON.stringify({ message: 'Action logged successfully' }),
        });
      } catch (error) {
        console.error('Error logging action:', error);
        reject({
          statusCode: 500,
          body: JSON.stringify({ message: 'Error logging action' }),
        });
      }
    });
  });
};
