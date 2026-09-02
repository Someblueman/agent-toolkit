pub mod baseline_rc_refcell;
pub mod simplified_arena;

#[cfg(test)]
mod tests {
    use super::baseline_rc_refcell::RcGraph;
    use super::simplified_arena::ArenaGraph;

    #[test]
    fn test_dag_sum_parity() {
        // Build Baseline Graph: Root -> (A, B), A -> C, B -> C
        let mut rc_g = RcGraph::new();
        let root_rc = rc_g.add_node("root", 10);
        let a_rc = rc_g.add_node("A", 20);
        let b_rc = rc_g.add_node("B", 30);
        let c_rc = rc_g.add_node("C", 40);

        RcGraph::add_dependency(&root_rc, &a_rc);
        RcGraph::add_dependency(&root_rc, &b_rc);
        RcGraph::add_dependency(&a_rc, &c_rc);
        RcGraph::add_dependency(&b_rc, &c_rc);

        // Build Simplified Graph: Same topology
        let mut arena_g = ArenaGraph::new();
        let root_ar = arena_g.add_node("root", 10);
        let a_ar = arena_g.add_node("A", 20);
        let b_ar = arena_g.add_node("B", 30);
        let c_ar = arena_g.add_node("C", 40);

        arena_g.add_dependency(root_ar, a_ar).unwrap();
        arena_g.add_dependency(root_ar, b_ar).unwrap();
        arena_g.add_dependency(a_ar, c_ar).unwrap();
        arena_g.add_dependency(b_ar, c_ar).unwrap();

        // Evaluate sums (10 + 20 + 30 + 40 = 100)
        let sum_rc = rc_g.evaluate_sum(&root_rc).expect("Baseline sum failed");
        let sum_ar = arena_g.evaluate_sum(root_ar).expect("Arena sum failed");

        assert_eq!(sum_rc, 100);
        assert_eq!(sum_ar, 100);
        assert_eq!(sum_rc, sum_ar, "Parity check failed on DAG sum evaluation!");
    }

    #[test]
    fn test_cycle_detection_parity() {
        // Build Baseline Graph with cycle: A -> B -> C -> A
        let mut rc_g = RcGraph::new();
        let a_rc = rc_g.add_node("A", 5);
        let b_rc = rc_g.add_node("B", 10);
        let c_rc = rc_g.add_node("C", 15);

        RcGraph::add_dependency(&a_rc, &b_rc);
        RcGraph::add_dependency(&b_rc, &c_rc);
        RcGraph::add_dependency(&c_rc, &a_rc);

        // Build Simplified Graph with cycle: A -> B -> C -> A
        let mut arena_g = ArenaGraph::new();
        let a_ar = arena_g.add_node("A", 5);
        let b_ar = arena_g.add_node("B", 10);
        let c_ar = arena_g.add_node("C", 15);

        arena_g.add_dependency(a_ar, b_ar).unwrap();
        arena_g.add_dependency(b_ar, c_ar).unwrap();
        arena_g.add_dependency(c_ar, a_ar).unwrap();

        let res_rc = rc_g.evaluate_sum(&a_rc);
        let res_ar = arena_g.evaluate_sum(a_ar);

        assert!(res_rc.is_err(), "Baseline should detect cycle");
        assert!(res_ar.is_err(), "Arena should detect cycle");

        // Verify error details
        match (res_rc, res_ar) {
            (
                Err(super::baseline_rc_refcell::GraphError::CycleDetected(node_rc)),
                Err(super::simplified_arena::GraphError::CycleDetected(node_ar)),
            ) => {
                assert_eq!(node_rc, node_ar, "Both must identify the same cycle origin node!");
            }
            other => panic!("Unexpected result pairing: {:?}", other),
        }
    }

    #[test]
    fn test_single_node() {
        let mut rc_g = RcGraph::new();
        let r_rc = rc_g.add_node("solo", 42);

        let mut ar_g = ArenaGraph::new();
        let r_ar = ar_g.add_node("solo", 42);

        assert_eq!(rc_g.evaluate_sum(&r_rc).unwrap(), 42);
        assert_eq!(ar_g.evaluate_sum(r_ar).unwrap(), 42);
    }
}
