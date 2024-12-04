import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load the CSV file
file_path_bandit_participant1 = './user_logs/yKDX3owrsw/interaction_log.csv'
df = pd.read_csv(file_path_bandit_participant1)


# --------------------- EMPIRICAL REWARD PROBS -------------------------------------------------

# Initialize counters for rewards and total selections for each arm
reward_counts = {0: 0, 1: 0}  # 0: Charismatic, 1: Uncharismatic
total_counts = {0: 0, 1: 0}

# Loop through the data to count rewards and selections
for index, row in df.iterrows():
    arm = row['ChosenArm']  # The chosen arm (0 or 1)
    reward = row['ObservedReward']  # The reward (1 or 0)
    
    # Update counts
    reward_counts[arm] += reward  # Increment reward count for the chosen arm
    total_counts[arm] += 1       # Increment total selection count for the chosen arm

# Compute the empirical probabilities for each arm
reward_probabilities = {
    arm: (reward_counts[arm] / total_counts[arm]) if total_counts[arm] > 0 else 0
    for arm in reward_counts
}

# Print the computed probabilities
print("Empirical Reward Probabilities:")
print(f"Charismatic (0): {reward_probabilities[0]:.2f}")
print(f"Uncharismatic (1): {reward_probabilities[1]:.2f}")

# --------------------- EMPIRICAL REWARD PROBS -------------------------------------------------

# --------------------- REWARD PROBS for ARM BASED ON CONTEXT -------------------------------------------------

# Ensure 'ContextFeatures' column is processed as numeric
df['ContextFeatures'] = df['ContextFeatures'].str.strip('[]').astype(float)

# Define the context classification function based on your thresholds
def classify_context(value):
    if np.isclose(value, 0.1, atol=0.1):  # Low interactivity
        return "low"
    elif np.isclose(value, 0.5, atol=0.1):  # Medium interactivity
        return "medium"
    elif np.isclose(value, 0.9, atol=0.1):  # High interactivity
        return "high"
    else:
        raise ValueError(f"Unexpected context value: {value}")

# Apply context classification to the data
df['Context'] = df['ContextFeatures'].apply(classify_context)

# Empirical reward probabilities for Charismatic (0) and Uncharismatic (1) arms
reward_probs = {
    0: 0.82,  # Charismatic
    1: 0.90   # Uncharismatic
}

# Initialize variables for tracking rewards, regret, and cumulative results
n_sim_steps = len(df)
cumulative_rewards = []
chosen_arms = []
rewards = []
step_regret = []
cumulative_regret = []

# Iterate through each step (row in your CSV data)
for t in range(n_sim_steps):
    # Get the context and chosen arm from the data
    context = df.loc[t, 'Context']
    chosen_arm = df.loc[t, 'ChosenArm']
    
    # Simulate reward based on the chosen arm and context
    reward_prob = reward_probs[chosen_arm]
    reward = np.random.binomial(1, reward_prob)

    # Track results
    chosen_arms.append(chosen_arm)
    rewards.append(reward)
    cumulative_rewards.append(sum(rewards))

    # Calculate regret
    # 1. Calculate the optimal reward for the current context (based on reward probabilities for both arms)
    reward_charismatic = reward_probs[0]  # Charismatic arm reward
    reward_uncharismatic = reward_probs[1]  # Uncharismatic arm reward
    optimal_reward = max(reward_charismatic, reward_uncharismatic)

    # 2. Calculate regret
    regret = optimal_reward - reward_prob
    step_regret.append(regret)
    cumulative_regret.append(sum(step_regret))

    # Output result for each step (optional)
    print(f"Step {t+1}: Context = {context}, Chosen Arm = {chosen_arm}, Reward = {reward}, Regret = {regret}")

# Plot results
steps = np.arange(1, n_sim_steps + 1)

# Create figure for plots
plt.figure(figsize=(12, 6))

# Plot cumulative rewards
plt.subplot(3, 1, 1)
plt.plot(steps, cumulative_rewards, label='Cumulative Rewards')
plt.xlabel('Step')
plt.ylabel('Cumulative Rewards')
plt.title('Cumulative Rewards Over Time')
plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
plt.legend()

# Plot chosen arms
plt.subplot(3, 1, 2)
plt.scatter(steps, chosen_arms, alpha=0.6, label='Arm Chosen')
plt.yticks([0, 1], ['Charismatic', 'Uncharismatic'])
plt.xlabel('Step')
plt.ylabel('Chosen Arm')
plt.title('Arm Choices Over Time')
plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
plt.legend()

# Plot cumulative regret
plt.subplot(3, 1, 3)
plt.plot(steps, cumulative_regret, label='Cumulative Regret', color='red')
plt.xlabel('Step')
plt.ylabel('Cumulative Regret')
plt.title('Cumulative Regret Over Time')
plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
plt.legend()

# Display the plots
plt.tight_layout()
plt.show()




# --------------------- REWARD PROBS for ARM BASED ON CONTEXT -------------------------------------------------

# # Ensure 'ContextFeatures' column is processed as numeric
# df['ContextFeatures'] = df['ContextFeatures'].str.strip('[]').astype(float)

# def classify_context(value):
#     if np.isclose(value, 0.1, atol=0.1):  # Close to 0.1
#         return "low"
#     elif np.isclose(value, 0.5, atol=0.1):  # Close to 0.5
#         return "medium"
#     elif np.isclose(value, 0.9, atol=0.1):  # Close to 0.9
#         return "high"
#     else:
#         raise ValueError(f"Unexpected context value: {value}")


# # Apply context classification to the data
# df['Context'] = df['ContextFeatures'].apply(classify_context)

# # Empirical reward probabilities for Charismatic (0) and Uncharismatic (1) arms
# reward_probs = {
#     0: 0.82,  # Charismatic
#     1: 0.90   # Uncharismatic
# }

# # Initialize variables for tracking rewards, regret, and cumulative results
# n_sim_steps = len(df)
# cumulative_rewards = []
# chosen_arms = []
# rewards = []
# step_regret = []
# cumulative_regret = []

# # Iterate through each step (row in your CSV data)
# for t in range(n_sim_steps):
#     # Get the context and chosen arm from the data
#     context = df.loc[t, 'ContextFeatures']
#     chosen_arm = df.loc[t, 'ChosenArm']
    
#     # Simulate reward based on the chosen arm and context
#     reward_prob = reward_probs[chosen_arm]
#     reward = np.random.binomial(1, reward_prob)

#     # Track results
#     chosen_arms.append(chosen_arm)
#     rewards.append(reward)
#     cumulative_rewards.append(sum(rewards))

#     # Calculate regret
#     # 1. Calculate the optimal reward for the current context (based on reward probabilities for both arms)
#     reward_charismatic = reward_probs[0]  # Charismatic arm reward
#     reward_uncharismatic = reward_probs[1]  # Uncharismatic arm reward
#     optimal_reward = max(reward_charismatic, reward_uncharismatic)

#     # 2. Calculate regret
#     regret = optimal_reward - reward_prob
#     step_regret.append(regret)
#     cumulative_regret.append(sum(step_regret))

#     # Output result for each step (optional)
#     print(f"Step {t+1}: Context = {context}, Chosen Arm = {chosen_arm}, Reward = {reward}, Regret = {regret}")

# # Plot results
# steps = np.arange(1, n_sim_steps + 1)

# # Create figure for plots
# plt.figure(figsize=(12, 6))

# # Plot cumulative rewards
# plt.subplot(3, 1, 1)
# plt.plot(steps, cumulative_rewards, label='Cumulative Rewards')
# plt.xlabel('Step')
# plt.ylabel('Cumulative Rewards')
# plt.title('Cumulative Rewards Over Time')
# plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
# plt.legend()

# # Plot chosen arms
# plt.subplot(3, 1, 2)
# plt.scatter(steps, chosen_arms, alpha=0.6, label='Arm Chosen')
# plt.yticks([0, 1], ['Charismatic', 'Uncharismatic'])
# plt.xlabel('Step')
# plt.ylabel('Chosen Arm')
# plt.title('Arm Choices Over Time')
# plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
# plt.legend()

# # Plot cumulative regret
# plt.subplot(3, 1, 3)
# plt.plot(steps, cumulative_regret, label='Cumulative Regret', color='red')
# plt.xlabel('Step')
# plt.ylabel('Cumulative Regret')
# plt.title('Cumulative Regret Over Time')
# plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
# plt.legend()

# # Display the plots
# plt.tight_layout()
# plt.show()


# # import numpy as np
# # import matplotlib.pyplot as plt
# # import csv
# # import os


# # # Initialize lists to hold column data
# # time = []
# # reward = []
# # arm = []






# # with open(user_log_path, 'r') as file:
# #     csv_reader = csv.reader(file)
# #     for row in csv_reader:
# #         print(row)



# # # Plot the data
# # # plt.figure(figsize=(10, 6))
# # # plt.plot(time, , marker='o', label="User Interaction")
# # # plt.xlabel('Time (seconds)')
# # # plt.ylabel('Interaction')
# # # plt.title('User Interaction Log')
# # # plt.legend()
# # # plt.show()


