//! Simplified Implementation: Flat Generational Arena Vector & `thiserror`.
//!
//! Simplification Benefits:
//! 1. Memory is contiguous in a single `Vec<ArenaNode>` (cache-friendly, zero leak risk).
//! 2. References are plain `NodeId(usize)` index handles (zero `Rc`, zero `RefCell`, zero runtime borrow panics).
//! 3. Unified descriptive error handling with `#[derive(thiserror::Error)]`.

use thiserror::Error;

#[derive(Error, Debug, PartialEq, Eq)]
pub enum GraphError {
    #[error("Cycle detected in graph at node '{0}'")]
    CycleDetected(String),

    #[error("Node index {0} not found in arena")]
    InvalidNodeIndex(usize),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId(pub usize);

#[derive(Debug, Clone)]
pub struct ArenaNode {
    pub name: String,
    pub value: i64,
    pub dependencies: Vec<NodeId>,
}

#[derive(Debug, Default)]
pub struct ArenaGraph {
    nodes: Vec<ArenaNode>,
}

impl ArenaGraph {
    pub fn new() -> Self {
        Self { nodes: Vec::new() }
    }

    pub fn add_node(&mut self, name: &str, value: i64) -> NodeId {
        let id = NodeId(self.nodes.len());
        self.nodes.push(ArenaNode {
            name: name.to_string(),
            value,
            dependencies: Vec::new(),
        });
        id
    }

    pub fn add_dependency(&mut self, from: NodeId, to: NodeId) -> Result<(), GraphError> {
        if from.0 >= self.nodes.len() {
            return Err(GraphError::InvalidNodeIndex(from.0));
        }
        if to.0 >= self.nodes.len() {
            return Err(GraphError::InvalidNodeIndex(to.0));
        }
        self.nodes[from.0].dependencies.push(to);
        Ok(())
    }

    pub fn get_node(&self, id: NodeId) -> Option<&ArenaNode> {
        self.nodes.get(id.0)
    }

    /// Evaluates total sum of reachable nodes, checking for cycles without dynamic allocations or locks.
    pub fn evaluate_sum(&self, root: NodeId) -> Result<i64, GraphError> {
        if root.0 >= self.nodes.len() {
            return Err(GraphError::InvalidNodeIndex(root.0));
        }

        // State: 0 = unvisited, 1 = visiting (in recursion stack), 2 = visited
        let mut state = vec![0u8; self.nodes.len()];
        self.eval_dfs(root, &mut state)
    }

    fn eval_dfs(&self, current: NodeId, state: &mut [u8]) -> Result<i64, GraphError> {
        let idx = current.0;
        if state[idx] == 1 {
            return Err(GraphError::CycleDetected(self.nodes[idx].name.clone()));
        }
        if state[idx] == 2 {
            return Ok(0);
        }

        state[idx] = 1;
        let mut total = self.nodes[idx].value;

        for &dep in &self.nodes[idx].dependencies {
            total += self.eval_dfs(dep, state)?;
        }

        state[idx] = 2;
        Ok(total)
    }
}
