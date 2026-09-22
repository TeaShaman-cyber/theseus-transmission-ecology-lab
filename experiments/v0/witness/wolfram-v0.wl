Module[
  {g, b, rank, nullity, h1, h1null, a, k0, rho, sub, super, assoc},
  g = Graph[
    {
      DirectedEdge["n1", "n2"],
      DirectedEdge["n2", "n3"],
      DirectedEdge["n3", "n1"],
      DirectedEdge["n3", "n4"],
      DirectedEdge["n4", "n1"]
    },
    DirectedEdges -> True
  ];
  b = Normal[IncidenceMatrix[g]];
  rank = MatrixRank[b];
  nullity = Length[EdgeList[g]] - rank;
  h1 = Transpose[b].b;
  h1null = Length[h1] - MatrixRank[h1];
  a = Transpose[Normal[AdjacencyMatrix[g]]];
  k0 = KroneckerProduct[a, IdentityMatrix[2]];
  rho = Max[Abs[Eigenvalues[N[k0, 30]]]];
  sub = Max[Abs[Eigenvalues[N[(0.8/rho) k0, 30]]]];
  super = Max[Abs[Eigenvalues[N[(1.2/rho) k0, 30]]]];
  assoc = <|
    "vertex_count" -> VertexCount[g],
    "edge_count" -> EdgeCount[g],
    "weak_component_count" -> Length[WeaklyConnectedGraphComponents[g]],
    "cycle_rank_beta1" -> (
      EdgeCount[g] - VertexCount[g] + Length[WeaklyConnectedGraphComponents[g]]
    ),
    "incidence_rank" -> rank,
    "incidence_nullity" -> nullity,
    "hodge1_nullity" -> h1null,
    "base_spectral_radius" -> N[rho, 20],
    "subcritical_spectral_radius" -> N[sub, 20],
    "supercritical_spectral_radius" -> N[super, 20],
    "subcritical_below_one" -> TrueQ[sub < 1],
    "supercritical_above_one" -> TrueQ[super > 1]
  |>;
  ExportString[assoc, "RawJSON"]
]
