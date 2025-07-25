# solution-object-detection

## Adding New Nodes

Follow these steps to properly integrate new nodes into the solution:

### 1. Create Node Component

Create a new node in `src/components/` or in the SDK (`supervisely/solution/components/...`):

- **Automation**: If the node has automation capabilities, ensure automation details are saved in `DataJson`. You can use the `Automation` or `AutomationWidget` classes from `supervisely/solution/base_nodes.py`.
- **History**: If the node maintains task history, all tasks must be saved in `DataJson`. You can use the `SolutionTasksHistory` class from `supervisely/solution/components/tasks_history.py`.
- **Node Definition**: Inherit from `SolutionElement` class to define the node's properties and behavior (e.g., title, icon, tooltip, card width, etc.). Create a `self.card` (`SolutionCard`), `self.node` (`SolutionCardNode`) attributes to represent the node visually and manage its layout.

### 2. Register Node

1. Initialize and add the new node to the appropriate location in `src/nodes/`.
2. Define the node's position in the workflow.
3. Update graph layout:
   - Add the node to the graph in `src/graph_builder.py`
   - Specify all incoming and outgoing connections

### 4. Handle Dependencies

If the node has dependencies or triggers other nodes, implement the logic in `src/main.py`:

- Handle node dependencies
- Manage node triggering mechanisms
- Ensure proper execution order
