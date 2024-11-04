const express = require('express');
const cors = require('cors');
const { MongoClient } = require('mongodb');

const app = express();
const PORT = process.env.PORT || 3000;
const mongoUrl = 'mongodb://localhost:27017'; // Adjust if necessary
const dbName = 'userLogsDB';

// allow to receive requests from my front end hosted at netlify.app:
app.use(cors({
    origin: 'https://drawingisfun.netlify.app' // Allow requests from your frontend URL
}));

app.use(express.json());

let db;

// Connect to MongoDB
MongoClient.connect(mongoUrl) // Removed deprecated options
    .then(client => {
        console.log('Connected to MongoDB');
        db = client.db(dbName);
    })
    .catch(error => console.error(error));

// Handle incoming requests to log user actions
app.post('/logUserAction', (req, res) => {
    const { action, timestamp, additionalData } = req.body;

    // Log the action to the console
    console.log(`Received Action: ${action} at ${timestamp}`);

    // Insert the log into the MongoDB collection
    db.collection('DataCollections').insertOne({ action, timestamp, additionalData })
        .then(result => {
            console.log("Insert successful:", result);
            res.status(200).send({ message: "Action logged successfully" });
        })
        .catch(error => {
            console.error("Error inserting into the database:", error);
            res.status(500).send({ message: "Error logging action" });
        });
});


// Allow fetching logged user actions
app.get('/getUserActions', (req, res) => {
    db.collection('actions').find({}).toArray()
        .then(actions => {
            res.status(200).send(actions);
        })
        .catch(error => {
            console.error("Error retrieving actions:", error);
            res.status(500).send({ message: "Error retrieving actions" });
        });
});

// Start server
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});

// const express = require('express');
// const cors = require('cors');
// const { MongoClient } = require('mongodb');

// const app = express();
// const PORT = process.env.PORT || 3000;
// const mongoUrl = 'mongodb://localhost:27017'; // Adjust if necessary
// const dbName = 'userLogsDB';

// app.use(express.json());
// app.use(cors());

// let db;

// // Connect to MongoDB
// MongoClient.connect(mongoUrl, { useNewUrlParser: true, useUnifiedTopology: true })
//     .then(client => {
//         console.log('Connected to MongoDB');
//         db = client.db(dbName);
//     })
//     .catch(error => console.error(error));


// //handle incoming requests to log user actions:
// app.post('/logUserAction', (req, res) => {
//     const { action, timestamp, additionalData } = req.body;

//     // Log the action to the console
//     console.log(`Received Action: ${action} at ${timestamp}`);

//     // Insert the log into the MongoDB collection
//     db.collection('actions').insertOne({ action, timestamp, additionalData })
//         .then(result => {
//             res.status(200).send({ message: "Action logged successfully" });
//         })
//         .catch(error => {
//             console.error("Error inserting into the database:", error);
//             res.status(500).send({ message: "Error logging action" });
//         });
// });

// //to allow fetching logged user actions:
// app.get('/getUserActions', (req, res) => {
//     db.collection('actions').find({}).toArray()
//         .then(actions => {
//             res.status(200).send(actions);
//         })
//         .catch(error => {
//             console.error("Error retrieving actions:", error);
//             res.status(500).send({ message: "Error retrieving actions" });
//         });
// });

// // start server: 
// app.listen(PORT, () => {
//     console.log(`Server is running on port ${PORT}`);
// });



// // const express = require('express');
// // const cors = require('cors');
// // const app = express();
// // const PORT = process.env.PORT || 3000;

// // // Middleware to parse JSON bodies
// // app.use(express.json());
// // app.use(cors()); // Enable CORS

// // // Endpoint to log user actions
// // app.post('/logUserAction', (req, res) => {
// //     const { action, timestamp } = req.body;

// //     // Log the action to the console (you can also log it to a database here)
// //     console.log(`Received Action: ${action} at ${timestamp}`);

// //     // Respond with a success message
// //     res.status(200).send({ message: "Action logged successfully" });
// // });

// // // Start the server
// // app.listen(PORT, () => {
// //     console.log(`Server is running on port ${PORT}`);
// // });
